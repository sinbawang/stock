from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCKERFILE = ROOT / "Dockerfile"


def _completed_process_succeeded(command: list[str], *, cwd: Path) -> bool:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.returncode == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the local image and deploy the Chanlun API service to CloudBase Run."
    )
    parser.add_argument(
        "--env-id",
        default=os.environ.get("CLOUDBASE_ENV_ID") or os.environ.get("TCB_ENV_ID"),
        help="CloudBase environment ID",
    )
    parser.add_argument(
        "--service-name",
        default=os.environ.get("CLOUDBASE_SERVICE_NAME") or "chanlun-stock-service",
        help="Existing CloudBase Run service name",
    )
    parser.add_argument(
        "--deploy-path",
        default=str(ROOT),
        help="Project root passed to tcb run deploy --path",
    )
    parser.add_argument(
        "--target-dir",
        default=".",
        help="Target directory inside deploy path passed to tcb run deploy --targetDir",
    )
    parser.add_argument(
        "--dockerfile",
        default=str(DEFAULT_DOCKERFILE),
        help="Dockerfile path",
    )
    parser.add_argument(
        "--image-tag",
        default="chanlun-stock-service:local",
        help="Local image tag used for the validation build",
    )
    parser.add_argument(
        "--container-port",
        type=int,
        default=8000,
        help="Container listening port",
    )
    parser.add_argument("--cpu", default="0.5", help="CloudBase Run CPU spec")
    parser.add_argument("--mem", default="1", help="CloudBase Run memory spec in GB")
    parser.add_argument("--min-num", type=int, default=0, help="Minimum replica count")
    parser.add_argument("--max-num", type=int, default=2, help="Maximum replica count")
    parser.add_argument(
        "--region",
        default=os.environ.get("CLOUDBASE_REGION") or os.environ.get("TCB_REGION") or "ap-guangzhou",
        help="CloudBase region forwarded to the container runtime",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("CLOUDBASE_APIKEY"),
        help="CloudBase admin API key injected into the container runtime",
    )
    parser.add_argument(
        "--set-env",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="Additional runtime env vars injected into the container",
    )
    parser.add_argument(
        "--skip-local-build",
        action="store_true",
        help="Skip the local docker build validation step",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved commands without executing them",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Do not pass --noConfirm to tcb run deploy",
    )
    return parser.parse_args()


def find_cli_command() -> str:
    for candidate in ("tcb", "cloudbase"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    raise SystemExit(
        "CloudBase CLI is not installed. Run `npm i -g @cloudbase/cli`, then `tcb login` or `tcb login --key`."
    )


def detect_cli_mode(cli_command: str, *, cwd: Path) -> str:
    if _completed_process_succeeded([cli_command, "cloudrun", "-h"], cwd=cwd):
        return "cloudrun"
    return "run"


def ensure_file(path: Path, label: str) -> Path:
    resolved = path.resolve()
    if not resolved.exists():
        raise SystemExit(f"{label} does not exist: {resolved}")
    return resolved


def parse_set_env(entries: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for item in entries:
        key, separator, value = item.partition("=")
        key = key.strip()
        if not separator or not key:
            raise SystemExit(f"Invalid --set-env value: {item}. Expected KEY=VALUE.")
        if "&" in key or "=" in key or "&" in value:
            raise SystemExit(
                f"Unsupported --set-env value: {item}. Keys and values cannot contain '&', and keys cannot contain '='."
            )
        parsed[key] = value
    return parsed


def build_runtime_env(args: argparse.Namespace) -> dict[str, str]:
    env_map = {
        "CLOUDBASE_ENV_ID": args.env_id,
        "CLOUDBASE_REGION": args.region,
    }
    if args.api_key:
        if "&" in args.api_key:
            raise SystemExit("CLOUDBASE_APIKEY cannot contain '&' when passed through --envParams.")
        env_map["CLOUDBASE_APIKEY"] = args.api_key
    env_map.update(parse_set_env(args.set_env))
    return {key: value for key, value in env_map.items() if value not in (None, "")}


def format_env_params(env_map: dict[str, str]) -> str:
    return "&".join(f"{key}={value}" for key, value in env_map.items())


def display_command(command: list[str]) -> str:
    redacted: list[str] = []
    for item in command:
        if "CLOUDBASE_APIKEY=" in item:
            prefix, _, value = item.partition("CLOUDBASE_APIKEY=")
            tail = value[:6] + "..." if value else ""
            item = prefix + "CLOUDBASE_APIKEY=" + tail
        redacted.append(shlex.quote(item))
    return " ".join(redacted)


def run_command(command: list[str], *, cwd: Path, dry_run: bool) -> None:
    print(display_command(command))
    if dry_run:
        return
    completed = subprocess.run(command, cwd=str(cwd), check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def service_bootstrap_message(args: argparse.Namespace) -> str:
    console_url = "https://console.cloud.tencent.com/tcbr"
    bootstrap_lines = [
        f"CloudBase Run service `{args.service_name}` does not exist in env `{args.env_id}`.",
        "",
        "Create it once in the CloudBase console, then rerun this command.",
        f"Console: {console_url}",
        "",
        "Recommended bootstrap values:",
        f"- Service name: {args.service_name}",
        f"- Container port: {args.container_port}",
        f"- CPU: {args.cpu}",
        f"- Memory: {args.mem} GB",
        f"- Min replicas: {args.min_num}",
        f"- Max replicas: {args.max_num}",
        f"- Deploy path: {Path(args.deploy_path).resolve()}",
        f"- Dockerfile: {Path(args.dockerfile).resolve()}",
        "",
        "Quick verification after creation:",
        f"- tcb --env-id {args.env_id} cloudrun list --serviceName {args.service_name} --json",
    ]
    return "\n".join(bootstrap_lines)


def build_service_list_command(args: argparse.Namespace, *, cli_command: str, cli_mode: str) -> list[str]:
    if cli_mode == "cloudrun":
        return [
            cli_command,
            "--env-id",
            args.env_id,
            "cloudrun",
            "list",
            "--serviceName",
            args.service_name,
            "--json",
        ]
    return [
        cli_command,
        "run",
        "service:list",
        "-e",
        args.env_id,
        "-s",
        args.service_name,
        "--json",
    ]


def ensure_remote_service_exists(
    args: argparse.Namespace,
    *,
    cli_command: str,
    cli_mode: str,
    cwd: Path,
    dry_run: bool,
) -> None:
    command = build_service_list_command(args, cli_command=cli_command, cli_mode=cli_mode)
    print(display_command(command))
    if dry_run:
        print("Dry run skips remote service existence check.")
        return

    completed = subprocess.run(
        command,
        cwd=str(cwd),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip()
        stdout = completed.stdout.strip()
        detail = stderr or stdout or f"CloudBase CLI exited with code {completed.returncode}."
        raise SystemExit(f"Failed to query CloudBase Run service state.\n{detail}")

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(
            "CloudBase CLI returned non-JSON output during service existence check.\n"
            f"Output:\n{completed.stdout.strip()}"
        ) from exc

    if cli_mode == "cloudrun":
        data = payload.get("data")
        if isinstance(data, dict):
            server_list = data.get("ServerList") or []
            if isinstance(server_list, list) and server_list:
                return
    else:
        data = payload.get("data")
        if isinstance(data, list) and data:
            return

    raise SystemExit(service_bootstrap_message(args))


def build_local_image(args: argparse.Namespace, *, cwd: Path) -> None:
    docker = shutil.which("docker")
    if not docker:
        raise SystemExit("Docker is not installed or not on PATH. Use --skip-local-build to bypass the local image build.")

    dockerfile_path = ensure_file(Path(args.dockerfile), "Dockerfile")
    command = [
        docker,
        "build",
        "-f",
        str(dockerfile_path),
        "-t",
        args.image_tag,
        str(cwd),
    ]
    run_command(command, cwd=cwd, dry_run=args.dry_run)


def deploy_service(args: argparse.Namespace, *, cli_command: str, cwd: Path) -> None:
    runtime_env = build_runtime_env(args)
    deploy_path = ensure_file(Path(args.deploy_path), "Deploy path")
    cli_mode = detect_cli_mode(cli_command, cwd=cwd)

    if cli_mode == "cloudrun":
        if runtime_env:
            print(
                "Using CloudBase CLI cloudrun mode. Keep CLOUDBASE_ENV_ID / CLOUDBASE_REGION / CLOUDBASE_APIKEY configured in the CloudBase console, "
                "because cloudrun deploy does not update runtime env vars inline like the older run deploy command."
            )
        command = [
            cli_command,
            "--env-id",
            args.env_id,
            "cloudrun",
            "deploy",
            "-s",
            args.service_name,
            "--port",
            str(args.container_port),
            "--source",
            str(deploy_path),
        ]
        if not args.confirm:
            command.append("--force")
        run_command(command, cwd=deploy_path, dry_run=args.dry_run)
        return

    env_params = format_env_params(runtime_env)
    dockerfile_path = ensure_file(Path(args.dockerfile), "Dockerfile")
    command = [
        cli_command,
        "run",
        "deploy",
        "-e",
        args.env_id,
        "-s",
        args.service_name,
        "--path",
        str(deploy_path),
        "--targetDir",
        args.target_dir,
        "--dockerfile",
        dockerfile_path.name,
        "--containerPort",
        str(args.container_port),
        "--cpu",
        str(args.cpu),
        "--mem",
        str(args.mem),
        "--minNum",
        str(args.min_num),
        "--maxNum",
        str(args.max_num),
        "--envParams",
        env_params,
    ]
    if not args.confirm:
        command.append("--noConfirm")
    run_command(command, cwd=deploy_path, dry_run=args.dry_run)


def main() -> int:
    args = parse_args()
    if not args.env_id:
        raise SystemExit("Missing --env-id or CLOUDBASE_ENV_ID/TCB_ENV_ID.")

    cli_command = find_cli_command()
    repo_root = ROOT.resolve()
    cli_mode = detect_cli_mode(cli_command, cwd=repo_root)

    print(f"Using CloudBase CLI: {cli_command}")
    print(f"Detected CLI mode: {cli_mode}")
    print(f"Deploying service: {args.service_name}")
    print(f"Project root: {repo_root}")

    if not args.skip_local_build:
        build_local_image(args, cwd=repo_root)

    ensure_remote_service_exists(
        args,
        cli_command=cli_command,
        cli_mode=cli_mode,
        cwd=repo_root,
        dry_run=args.dry_run,
    )
    deploy_service(args, cli_command=cli_command, cwd=repo_root)
    print("Deployment command finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())