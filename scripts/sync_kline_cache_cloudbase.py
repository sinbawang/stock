from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import requests

from upload_miniapp_publish_bundle import (
    CloudBaseUploadError,
    CreatedApiKey,
    build_manifest,
    create_temporary_api_key,
    delete_temporary_api_key,
    get_upload_metadata,
    iter_local_files,
    load_previous_manifest,
    new_session,
    plan_uploads,
    upload_bytes,
    write_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = ROOT / "data" / "cache" / "kline"
DEFAULT_TARGET_DIR = ROOT / "data" / "cache" / "kline"
DEFAULT_MANIFEST_PATH = ROOT / "build" / "stock-kline-cache" / "cloudbase-upload-manifest.json"
DEFAULT_POINTER_PATH = ROOT / "build" / "stock-kline-cache" / "manifest-pointer.json"
DEFAULT_CLOUD_PREFIX = "stock-kline-cache/latest"


class CloudBaseSyncError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backup/restore local K-line cache to/from CloudBase storage."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    backup_parser = subparsers.add_parser("backup", help="Upload local kline cache to CloudBase storage")
    add_common_args(backup_parser)
    backup_parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Local cache directory to upload")
    backup_parser.add_argument(
        "--pointer-path",
        default=str(DEFAULT_POINTER_PATH),
        help="Local path to write manifest pointer metadata",
    )
    backup_parser.add_argument("--force-upload", action="store_true", help="Upload all files and ignore manifest diff")
    backup_parser.add_argument("--dry-run", action="store_true", help="Only build upload plan and manifest")

    restore_parser = subparsers.add_parser("restore", help="Restore local kline cache from CloudBase storage")
    add_common_args(restore_parser)
    restore_parser.add_argument("--target-dir", default=str(DEFAULT_TARGET_DIR), help="Local cache directory to restore")
    restore_parser.add_argument(
        "--pointer-path",
        default=str(DEFAULT_POINTER_PATH),
        help="Local pointer metadata path used to locate cloud manifest",
    )
    restore_parser.add_argument(
        "--manifest-file-id",
        default=None,
        help="Explicit cloud file id for _manifest.json (cloud://...)",
    )
    restore_parser.add_argument(
        "--fetch-manifest",
        action="store_true",
        help="Fetch cloud manifest first even if local manifest exists",
    )
    restore_parser.add_argument(
        "--clean-target",
        action="store_true",
        help="Delete target directory before restore",
    )
    restore_parser.add_argument(
        "--use-cli-download",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use CloudBase CLI `tcb storage download --dir` for restore (recommended)",
    )
    restore_parser.add_argument("--dry-run", action="store_true", help="Only print restore plan")

    check_parser = subparsers.add_parser("check", help="Run preflight checks for backup/restore")
    add_common_args(check_parser)
    check_parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR), help="Local source cache directory")
    check_parser.add_argument("--target-dir", default=str(DEFAULT_TARGET_DIR), help="Local target cache directory")
    check_parser.add_argument("--pointer-path", default=str(DEFAULT_POINTER_PATH), help="Local pointer metadata path")
    check_parser.add_argument(
        "--allow-not-logged-in",
        action="store_true",
        help="Do not fail the command when CloudBase CLI login is missing",
    )
    check_parser.add_argument("--json", action="store_true", help="Print check results as JSON")

    return parser.parse_args()


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--cloud-prefix",
        default=DEFAULT_CLOUD_PREFIX,
        help="Cloud storage prefix used for backup/restore",
    )
    parser.add_argument(
        "--manifest-path",
        default=str(DEFAULT_MANIFEST_PATH),
        help="Local manifest path",
    )
    parser.add_argument(
        "--env-id",
        default=os.environ.get("CLOUDBASE_ENV_ID") or os.environ.get("TCB_ENV_ID"),
        help="CloudBase environment ID",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("CLOUDBASE_REGION") or os.environ.get("TCB_REGION") or "ap-guangzhou",
        help="CloudBase region",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("CLOUDBASE_APIKEY"),
        help="CloudBase admin API key",
    )
    parser.add_argument(
        "--api-key-name",
        default="stock-kline-cache-sync",
        help="Temporary API key name when created automatically",
    )
    parser.add_argument(
        "--api-key-expire-in",
        type=int,
        default=7200,
        help="Temporary API key lifetime in seconds",
    )
    parser.add_argument(
        "--delete-created-api-key",
        action="store_true",
        help="Delete temporary API key after command finishes",
    )


def ensure_env_id(env_id: str | None, *, dry_run: bool) -> None:
    if not env_id and not dry_run:
        raise CloudBaseSyncError("Missing --env-id or CLOUDBASE_ENV_ID/TCB_ENV_ID.")


def build_admin_url(env_id: str, region: str) -> str:
    return f"https://{env_id}.{region}.tcb-api.tencentcloudapi.com/admin?env={env_id}"


def admin_headers(api_key: str, region: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "chanlun-stock-kline-sync/0.1",
        "X-SDK-Version": "chanlun-stock-kline-sync/0.1",
        "X-TCB-Region": region,
        "X-TCB-Source": "stock-kline-cache-sync,local",
    }


def admin_request(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    action: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    body = {"action": action, "envName": env_id, **payload}
    response = session.post(
        build_admin_url(env_id, region),
        headers=admin_headers(api_key, region),
        json=body,
        timeout=30,
    )
    response.raise_for_status()
    parsed = response.json()
    if parsed.get("code"):
        raise CloudBaseSyncError(f"{parsed.get('code')}: {parsed.get('message')}")
    return parsed


def get_download_url(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    cloud_path: str,
) -> str:
    payload_candidates: list[dict[str, Any]] = [
        {"file_list": [cloud_path]},
        {"fileList": [cloud_path]},
        {"fileid_list": [cloud_path]},
        {"fileIdList": [cloud_path]},
    ]

    response: dict[str, Any] | None = None
    last_error: Exception | None = None
    for payload in payload_candidates:
        try:
            response = admin_request(
                session,
                env_id=env_id,
                region=region,
                api_key=api_key,
                action="storage.batchGetDownloadUrl",
                payload=payload,
            )
            break
        except CloudBaseSyncError as exc:
            last_error = exc
            continue

    if response is None:
        if last_error is not None:
            raise CloudBaseSyncError(str(last_error))
        raise CloudBaseSyncError(f"Cannot request download metadata for {cloud_path}")

    data = response.get("data")

    items: list[Any] = []
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        for key in ("download_list", "downloadList", "fileList", "DownloadList", "list"):
            candidate = data.get(key)
            if isinstance(candidate, list):
                items = candidate
                break
    if not items:
        raise CloudBaseSyncError(f"No download metadata returned for {cloud_path}.")

    first = items[0]
    if isinstance(first, str) and first.strip():
        return first
    if isinstance(first, dict):
        for key in (
            "tempFileURL",
            "tempFileUrl",
            "download_url",
            "downloadUrl",
            "url",
            "fileUrl",
        ):
            value = first.get(key)
            if isinstance(value, str) and value.strip():
                return value
    raise CloudBaseSyncError(f"Cannot parse download URL for {cloud_path}: {first}")


def ensure_api_key(args: argparse.Namespace) -> tuple[str, CreatedApiKey | None]:
    if args.api_key:
        return str(args.api_key), None
    created = create_temporary_api_key(
        env_id=args.env_id,
        region=args.region,
        key_name=args.api_key_name,
        expire_in=args.api_key_expire_in,
    )
    print(f"created_api_key={created.key_id}")
    return created.api_key, created


def find_tcb_command() -> str:
    for candidate in ("tcb.cmd", "tcb", "cloudbase"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise CloudBaseSyncError("CloudBase CLI not found. Install @cloudbase/cli first.")


def ensure_tcb_logged_in(tcb_command: str, *, region: str, env_id: str) -> None:
    probe_command = [
        tcb_command,
        "--region",
        region,
        "--env-id",
        env_id,
        "env",
        "list",
        "--json",
    ]
    completed = subprocess.run(
        probe_command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode == 0:
        return

    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    lowered = output.lower()
    if "no valid identity information" in lowered or "login" in lowered:
        raise CloudBaseSyncError(
            "CloudBase CLI is not logged in. Run `tcb login` first, then retry restore. "
            "In restricted PowerShell environments, use the explicit command path: `tcb.cmd login`."
        )

    trimmed = output.strip()
    detail = trimmed if trimmed else f"exit code {completed.returncode}"
    raise CloudBaseSyncError(f"CloudBase CLI preflight failed: {detail}")


def restore_with_cli(args: argparse.Namespace, target_dir: Path) -> int:
    if not args.env_id:
        raise CloudBaseSyncError("Missing --env-id or CLOUDBASE_ENV_ID/TCB_ENV_ID.")

    tcb_command = find_tcb_command()
    ensure_tcb_logged_in(tcb_command, region=str(args.region), env_id=str(args.env_id))

    if args.clean_target and target_dir.exists():
        shutil.rmtree(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    cloud_dir = args.cloud_prefix.strip("/") + "/"
    command = [
        tcb_command,
        "--env-id",
        str(args.env_id),
        "--region",
        str(args.region),
        "storage",
        "download",
        cloud_dir,
        str(target_dir),
        "--dir",
    ]
    print("restore_command=" + " ".join(command))
    if args.dry_run:
        return 0

    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise CloudBaseSyncError(f"CloudBase CLI restore failed with exit code {completed.returncode}")
    return 0


def _check_result(name: str, ok: bool, detail: str, *, level: str = "required") -> dict[str, str | bool]:
    return {
        "name": name,
        "ok": ok,
        "level": level,
        "detail": detail,
    }


def command_check(args: argparse.Namespace) -> int:
    results: list[dict[str, str | bool]] = []

    source_dir = Path(args.source_dir).resolve()
    target_dir = Path(args.target_dir).resolve()
    pointer_path = Path(args.pointer_path).resolve()
    manifest_path = Path(args.manifest_path).resolve()

    env_id = str(args.env_id or "").strip()
    region = str(args.region or "").strip()
    api_key = str(args.api_key or "").strip()

    results.append(
        _check_result(
            "env_id",
            bool(env_id),
            "CLOUDBASE_ENV_ID/TCB_ENV_ID is set" if env_id else "Missing --env-id and CLOUDBASE_ENV_ID/TCB_ENV_ID",
        )
    )
    results.append(
        _check_result(
            "region",
            bool(region),
            f"region={region}" if region else "Missing --region and CLOUDBASE_REGION/TCB_REGION",
        )
    )

    source_exists = source_dir.exists()
    source_count = 0
    if source_exists:
        source_count = sum(1 for p in source_dir.rglob("*") if p.is_file())
    results.append(
        _check_result(
            "source_dir",
            source_exists,
            f"exists: {source_dir} (files={source_count})" if source_exists else f"missing: {source_dir}",
        )
    )
    results.append(
        _check_result(
            "target_dir_parent",
            target_dir.parent.exists(),
            f"parent exists: {target_dir.parent}" if target_dir.parent.exists() else f"parent missing: {target_dir.parent}",
        )
    )

    results.append(
        _check_result(
            "api_key_or_temp_credentials",
            bool(api_key) or bool(os.environ.get("TENCENT_SECRET_ID") and os.environ.get("TENCENT_SECRET_KEY")),
            "using CLOUDBASE_APIKEY or TENCENT_SECRET_ID/TENCENT_SECRET_KEY"
            if (api_key or (os.environ.get("TENCENT_SECRET_ID") and os.environ.get("TENCENT_SECRET_KEY")))
            else "Missing CLOUDBASE_APIKEY and missing TENCENT_SECRET_ID/TENCENT_SECRET_KEY",
            level="optional",
        )
    )

    results.append(
        _check_result(
            "pointer_file",
            pointer_path.exists(),
            f"found: {pointer_path}" if pointer_path.exists() else f"not found: {pointer_path}",
            level="optional",
        )
    )
    results.append(
        _check_result(
            "manifest_file",
            manifest_path.exists(),
            f"found: {manifest_path}" if manifest_path.exists() else f"not found: {manifest_path}",
            level="optional",
        )
    )

    tcb_command = ""
    try:
        tcb_command = find_tcb_command()
        results.append(_check_result("tcb_cli", True, f"found: {tcb_command}"))
    except CloudBaseSyncError as exc:
        results.append(_check_result("tcb_cli", False, str(exc)))

    logged_in_ok = False
    if tcb_command and env_id and region:
        try:
            ensure_tcb_logged_in(tcb_command, region=region, env_id=env_id)
            logged_in_ok = True
            results.append(_check_result("tcb_login", True, "CloudBase CLI login is valid"))
        except CloudBaseSyncError as exc:
            results.append(_check_result("tcb_login", False, str(exc)))
    elif not tcb_command:
        results.append(_check_result("tcb_login", False, "Skipped because CloudBase CLI is missing"))
    else:
        results.append(_check_result("tcb_login", False, "Skipped because env_id/region is missing"))

    if tcb_command and env_id and logged_in_ok:
        cloud_probe = [
            tcb_command,
            "--env-id",
            env_id,
            "--region",
            region,
            "storage",
            "list",
            args.cloud_prefix.strip("/") + "/",
            "--json",
        ]
        completed = subprocess.run(
            cloud_probe,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if completed.returncode == 0:
            results.append(
                _check_result(
                    "cloud_prefix_access",
                    True,
                    f"readable: {args.cloud_prefix}",
                )
            )
        else:
            detail = (completed.stdout or "") + "\n" + (completed.stderr or "")
            results.append(
                _check_result(
                    "cloud_prefix_access",
                    False,
                    detail.strip() or f"Failed to list {args.cloud_prefix}",
                )
            )
    else:
        results.append(
            _check_result(
                "cloud_prefix_access",
                False,
                "Skipped because CLI login/env is not ready",
            )
        )

    if args.json:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            status = "PASS" if item["ok"] else "FAIL"
            print(f"[{status}] {item['name']} ({item['level']}) - {item['detail']}")

    required_failures = [item for item in results if item["level"] == "required" and not item["ok"]]
    if args.allow_not_logged_in:
        required_failures = [item for item in required_failures if item["name"] != "tcb_login"]
    return 1 if required_failures else 0


def upload_manifest_file(
    session: requests.Session,
    *,
    env_id: str,
    region: str,
    api_key: str,
    cloud_prefix: str,
    manifest_path: Path,
) -> tuple[str, str]:
    cloud_path = f"{cloud_prefix.strip('/')}/_manifest.json"
    metadata = get_upload_metadata(
        session,
        env_id=env_id,
        region=region,
        api_key=api_key,
        cloud_path=cloud_path,
    )
    upload_bytes(session, cloud_path=cloud_path, local_path=manifest_path, metadata=metadata)
    file_id = str(metadata.get("fileId") or "")
    print(f"uploaded_manifest={cloud_path}")
    if file_id:
        print(f"manifest_file_id={file_id}")
    return cloud_path, file_id


def write_pointer(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def command_backup(args: argparse.Namespace) -> int:
    ensure_env_id(args.env_id, dry_run=args.dry_run)
    source_dir = Path(args.source_dir).resolve()
    if not source_dir.exists():
        raise CloudBaseSyncError(f"source dir does not exist: {source_dir}")
    manifest_path = Path(args.manifest_path).resolve()
    pointer_path = Path(args.pointer_path).resolve()

    files = iter_local_files(source_dir, args.cloud_prefix)
    if not files:
        raise CloudBaseSyncError(f"No files found under {source_dir}")

    previous_manifest = load_previous_manifest(manifest_path)
    upload_plan, skipped_uploads = plan_uploads(
        files,
        previous_manifest,
        env_id=args.env_id,
        region=args.region,
        cloud_prefix=args.cloud_prefix,
        force_upload=args.force_upload,
    )

    print(f"source={source_dir}")
    print(f"files={len(files)}")
    print(f"uploading={len(upload_plan)}")
    print(f"skipped={len(skipped_uploads)}")
    print(f"cloud_prefix={args.cloud_prefix}")
    if args.force_upload:
        print("force_upload=true")

    if args.dry_run:
        manifest = build_manifest(
            env_id=args.env_id or "",
            region=args.region,
            source_dir=source_dir,
            cloud_prefix=args.cloud_prefix,
            uploads=skipped_uploads
            + [
                {
                    "relative_path": item.relative_path,
                    "cloud_path": item.cloud_path,
                    "file_id": None,
                    "size": item.size,
                    "sha256": item.sha256,
                    "status": "planned",
                }
                for item in upload_plan
            ],
        )
        write_manifest(manifest_path, manifest)
        print(f"dry_run_manifest={manifest_path}")
        return 0

    api_key, created_api_key = ensure_api_key(args)
    session = new_session()
    uploads: list[dict[str, Any]] = list(skipped_uploads)
    try:
        for item in upload_plan:
            metadata = get_upload_metadata(
                session,
                env_id=args.env_id,
                region=args.region,
                api_key=api_key,
                cloud_path=item.cloud_path,
            )
            upload_bytes(session, cloud_path=item.cloud_path, local_path=item.local_path, metadata=metadata)
            uploads.append(
                {
                    "relative_path": item.relative_path,
                    "cloud_path": item.cloud_path,
                    "file_id": metadata["fileId"],
                    "size": item.size,
                    "sha256": item.sha256,
                    "status": "uploaded",
                }
            )
            print(f"uploaded {item.relative_path}")

        manifest = build_manifest(
            env_id=args.env_id,
            region=args.region,
            source_dir=source_dir,
            cloud_prefix=args.cloud_prefix,
            uploads=uploads,
        )
        write_manifest(manifest_path, manifest)
        print(f"manifest={manifest_path}")
        manifest_cloud_path, manifest_file_id = upload_manifest_file(
            session,
            env_id=args.env_id,
            region=args.region,
            api_key=api_key,
            cloud_prefix=args.cloud_prefix,
            manifest_path=manifest_path,
        )
        pointer_payload = {
            "env_id": args.env_id,
            "region": args.region,
            "cloud_prefix": args.cloud_prefix,
            "manifest_cloud_path": manifest_cloud_path,
            "manifest_file_id": manifest_file_id,
            "manifest_path": str(manifest_path),
        }
        write_pointer(pointer_path, pointer_payload)
        print(f"pointer={pointer_path}")
    finally:
        session.close()
        if created_api_key and args.delete_created_api_key:
            delete_temporary_api_key(env_id=args.env_id, region=args.region, key_id=created_api_key.key_id)
            print(f"deleted_api_key={created_api_key.key_id}")
    return 0


def download_file(url: str, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, timeout=120, stream=True) as response:
        response.raise_for_status()
        with destination.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 256):
                if chunk:
                    handle.write(chunk)


def fetch_manifest_from_cloud(
    *,
    session: requests.Session,
    env_id: str,
    region: str,
    api_key: str,
    cloud_prefix: str,
    manifest_file_id: str | None,
    manifest_path: Path,
) -> None:
    cloud_manifest = (manifest_file_id or "").strip() or f"{cloud_prefix.strip('/')}/_manifest.json"
    url = get_download_url(
        session,
        env_id=env_id,
        region=region,
        api_key=api_key,
        cloud_path=cloud_manifest,
    )
    download_file(url, manifest_path)
    print(f"downloaded_manifest={manifest_path}")


def read_pointer(pointer_path: Path) -> dict[str, Any] | None:
    if not pointer_path.exists():
        return None
    try:
        payload = json.loads(pointer_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def read_manifest(manifest_path: Path) -> dict[str, Any]:
    if not manifest_path.exists():
        raise CloudBaseSyncError(f"manifest not found: {manifest_path}")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CloudBaseSyncError(f"Invalid manifest file: {manifest_path}") from exc
    if not isinstance(payload, dict):
        raise CloudBaseSyncError(f"Invalid manifest payload: {manifest_path}")
    files = payload.get("files")
    if not isinstance(files, list):
        raise CloudBaseSyncError(f"Manifest has no files list: {manifest_path}")
    return payload


def command_restore(args: argparse.Namespace) -> int:
    ensure_env_id(args.env_id, dry_run=args.dry_run)
    target_dir = Path(args.target_dir).resolve()
    manifest_path = Path(args.manifest_path).resolve()
    pointer_path = Path(args.pointer_path).resolve()
    pointer = read_pointer(pointer_path)

    manifest_file_id = str(args.manifest_file_id or "").strip() or None
    if manifest_file_id is None and pointer:
        value = str(pointer.get("manifest_file_id") or "").strip()
        if value:
            manifest_file_id = value

    if args.use_cli_download:
        return restore_with_cli(args, target_dir)

    if args.dry_run and not manifest_path.exists() and not args.fetch_manifest:
        raise CloudBaseSyncError(
            "manifest file is missing for dry-run restore. Use --fetch-manifest or provide --manifest-path."
        )

    api_key: str | None = None
    created_api_key: CreatedApiKey | None = None
    session: requests.Session | None = None
    try:
        if args.fetch_manifest or not manifest_path.exists():
            api_key, created_api_key = ensure_api_key(args)
            session = new_session()
            fetch_manifest_from_cloud(
                session=session,
                env_id=args.env_id,
                region=args.region,
                api_key=api_key,
                cloud_prefix=args.cloud_prefix,
                manifest_file_id=manifest_file_id,
                manifest_path=manifest_path,
            )

        manifest = read_manifest(manifest_path)
        files = [item for item in manifest.get("files") if isinstance(item, dict)]
        planned = [item for item in files if str(item.get("relative_path") or "").strip()]
        print(f"manifest={manifest_path}")
        print(f"restore_files={len(planned)}")
        print(f"target_dir={target_dir}")

        if args.dry_run:
            return 0

        if args.clean_target and target_dir.exists():
            shutil.rmtree(target_dir)
        target_dir.mkdir(parents=True, exist_ok=True)

        if session is None:
            api_key, created_api_key = ensure_api_key(args)
            session = new_session()

        restored = 0
        for item in planned:
            relative = str(item.get("relative_path") or "").strip()
            file_id = str(item.get("file_id") or "").strip()
            cloud_path = str(item.get("cloud_path") or "").strip()
            identifier = file_id or cloud_path
            if not relative or not identifier:
                continue
            url = get_download_url(
                session,
                env_id=args.env_id,
                region=args.region,
                api_key=api_key,
                cloud_path=identifier,
            )
            local_path = target_dir / relative
            download_file(url, local_path)
            restored += 1
            print(f"restored {relative}")
        print(f"restored_files={restored}")
        return 0
    finally:
        if session is not None:
            session.close()
        if created_api_key and args.delete_created_api_key:
            delete_temporary_api_key(env_id=args.env_id, region=args.region, key_id=created_api_key.key_id)
            print(f"deleted_api_key={created_api_key.key_id}")


def main() -> int:
    args = parse_args()
    if args.command == "backup":
        return command_backup(args)
    if args.command == "restore":
        return command_restore(args)
    if args.command == "check":
        return command_check(args)
    raise CloudBaseSyncError(f"Unsupported command: {args.command}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (CloudBaseSyncError, CloudBaseUploadError, requests.RequestException) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
