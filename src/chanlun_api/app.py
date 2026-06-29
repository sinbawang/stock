from __future__ import annotations

from argparse import Namespace
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import traceback
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from batch_generate_and_send_portfolio_mixed_reports import load_holdings
from batch_prepare_chanlun_reports import run_batch_prepare
from refresh_holdings_publish_to_cloudbase import rebuild_publish_bundle, regenerate_holdings, upload_publish_bundle
from storage_layout import DATA_META_DIR, HOLDINGS_FILE, REPORTS_DIR


Timeframe = Literal["day", "60m", "30m", "15m", "5m"]
Market = Literal["ALL", "CN", "HK"]
PendingReverseMode = Literal["any", "effective_only", "tail_mixed"]
ZhongshuLevel = Literal["bi", "segment"]
JobKind = Literal["publish_refresh", "technical_refresh"]
JobStatus = Literal["queued", "running", "succeeded", "failed"]


def _now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _dedupe_timeframes(values: list[Timeframe]) -> list[Timeframe]:
    return list(dict.fromkeys(values))


def _normalize_technical_publish_timeframes(publish_timeframes: list[Timeframe] | None) -> list[Timeframe] | None:
    if not publish_timeframes:
        return None
    normalized = _dedupe_timeframes(publish_timeframes)
    if "day" not in normalized:
        normalized.append("day")
    return normalized


class PublishRefreshRequest(BaseModel):
    holdings_file: str = Field(default=str(HOLDINGS_FILE))
    market: Market = "ALL"
    symbols: list[str] | None = None
    limit: int | None = None
    reports_root: str = Field(default=str(REPORTS_DIR))
    publish_root: str = Field(default=str(ROOT / "build" / "miniapp-publish"))
    snapshot_stamp: str | None = None
    latest_only: bool = True
    skip_regenerate: bool = False
    skip_build: bool = False
    skip_upload: bool = False
    skip_gen_base: bool = True
    skip_gen_fund: bool = False
    fail_on_holding_error: bool = False
    parallelism: int = Field(default=max(1, min(4, os.cpu_count() or 1)), ge=1)
    pending_reverse_mode: PendingReverseMode = "any"
    day_bars: int = Field(default=600, ge=1)
    m60_bars: int = Field(default=600, ge=1)
    m30_bars: int = Field(default=600, ge=1)
    m15_bars: int = Field(default=600, ge=1)
    m5_bars: int = Field(default=600, ge=1)
    zhongshu_level: ZhongshuLevel = "bi"
    tech_timeframes: list[Timeframe] = Field(default_factory=lambda: ["day", "60m", "30m", "15m", "5m"])
    publish_timeframes: list[Timeframe] | None = None
    cloud_prefix: str = "miniapp-publish/latest"
    env_id: str | None = None
    region: str | None = None
    api_key: str | None = None
    api_key_name: str | None = None
    api_key_expire_in: int | None = Field(default=None, ge=1)
    delete_created_api_key: bool = False
    upload_dry_run: bool = False


class TechnicalRefreshRequest(BaseModel):
    holdings_file: str = Field(default=str(HOLDINGS_FILE))
    market: Market = "ALL"
    symbols: list[str] | None = None
    limit: int | None = None
    reports_root: str = Field(default=str(REPORTS_DIR))
    publish_root: str = Field(default=str(ROOT / "build" / "miniapp-publish"))
    snapshot_stamp: str | None = None
    latest_only: bool = True
    skip_build: bool = False
    skip_upload: bool = False
    day_start: str | None = None
    day_bars: int = Field(default=600, ge=1)
    m60_start: str | None = None
    m60_bars: int = Field(default=600, ge=1)
    m30_start: str | None = None
    m30_bars: int = Field(default=600, ge=1)
    m15_start: str | None = None
    m15_bars: int = Field(default=600, ge=1)
    m5_start: str | None = None
    m5_bars: int = Field(default=600, ge=1)
    pending_reverse_mode: PendingReverseMode = "any"
    zhongshu_level: ZhongshuLevel = "bi"
    tech_timeframes: list[Timeframe] = Field(default_factory=lambda: ["30m", "5m"])
    publish_timeframes: list[Timeframe] | None = None
    cloud_prefix: str = "miniapp-publish/latest"
    env_id: str | None = None
    region: str | None = None
    api_key: str | None = None
    api_key_name: str | None = None
    api_key_expire_in: int | None = Field(default=None, ge=1)
    delete_created_api_key: bool = False
    upload_dry_run: bool = False


class JobCreatedResponse(BaseModel):
    job_id: str
    kind: JobKind
    status: JobStatus
    created_at: str


class JobStateResponse(BaseModel):
    job_id: str
    kind: JobKind
    status: JobStatus
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    request: dict[str, Any]
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class _JobRecord:
    job_id: str
    kind: JobKind
    request: dict[str, Any]
    status: JobStatus = "queued"
    created_at: str = field(default_factory=_now_iso)
    started_at: str | None = None
    finished_at: str | None = None
    result: dict[str, Any] | None = None
    error: str | None = None


class _JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, _JobRecord] = {}
        self._lock = threading.Lock()

    def create(self, kind: JobKind, request: dict[str, Any]) -> _JobRecord:
        job = _JobRecord(job_id=uuid4().hex, kind=kind, request=request)
        with self._lock:
            self._jobs[job.job_id] = job
        return job

    def get(self, job_id: str) -> _JobRecord | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[_JobRecord]:
        with self._lock:
            return list(self._jobs.values())

    def update(self, job_id: str, **kwargs: Any) -> None:
        with self._lock:
            job = self._jobs[job_id]
            for key, value in kwargs.items():
                setattr(job, key, value)


@contextmanager
def _filtered_holdings_file(
    *,
    holdings_file: Path,
    market: Market,
    symbols: list[str] | None,
    limit: int | None,
):
    holdings = load_holdings(holdings_file, market_filter=market)
    if symbols:
        requested = {str(symbol).strip() for symbol in symbols if str(symbol).strip()}
        normalized = requested | {value.zfill(5) for value in requested} | {value.zfill(6) for value in requested}
        holdings = [
            holding
            for holding in holdings
            if holding.symbol in normalized or holding.symbol.zfill(5) in normalized or holding.symbol.zfill(6) in normalized
        ]
    if limit is not None:
        holdings = holdings[:limit]
    if not holdings:
        raise ValueError("No holdings matched the request")

    payload = {
        "markets": {
            "CN": [{"symbol": item.symbol, "name": item.name} for item in holdings if item.market == "CN"],
            "HK": [{"symbol": item.symbol, "name": item.name} for item in holdings if item.market == "HK"],
        }
    }
    DATA_META_DIR.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="service_holdings_", dir=str(DATA_META_DIR)) as temp_dir:
        path = Path(temp_dir) / "holdings.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        yield path, holdings


def _build_publish_namespace(
    *,
    holdings_file: str,
    reports_root: str,
    publish_root: str,
    snapshot_stamp: str | None,
    latest_only: bool,
    skip_build: bool,
    skip_upload: bool,
    publish_timeframes: list[Timeframe] | None,
    cloud_prefix: str,
    env_id: str | None,
    region: str | None,
    api_key: str | None,
    api_key_name: str | None,
    api_key_expire_in: int | None,
    delete_created_api_key: bool,
    upload_dry_run: bool,
) -> Namespace:
    return Namespace(
        holdings_file=holdings_file,
        reports_root=reports_root,
        publish_root=publish_root,
        snapshot_stamp=snapshot_stamp,
        latest_only=latest_only,
        skip_build=skip_build,
        skip_upload=skip_upload,
        publish_timeframes=tuple(_dedupe_timeframes(publish_timeframes)) if publish_timeframes else None,
        cloud_prefix=cloud_prefix,
        env_id=env_id,
        region=region,
        api_key=api_key,
        api_key_name=api_key_name,
        api_key_expire_in=api_key_expire_in,
        delete_created_api_key=delete_created_api_key,
        upload_dry_run=upload_dry_run,
    )


def _publish_build_and_upload(args: Namespace) -> dict[str, Any]:
    latest_dir = Path(args.publish_root) / "latest"
    if not args.skip_build:
        latest_dir = rebuild_publish_bundle(args)
    if not args.skip_upload:
        upload_publish_bundle(args, latest_dir)
    return {
        "publish_root": str(args.publish_root),
        "latest_dir": str(latest_dir),
        "cloud_prefix": args.cloud_prefix,
        "published_timeframes": list(args.publish_timeframes) if args.publish_timeframes else None,
    }


def _run_publish_refresh(request: PublishRefreshRequest) -> dict[str, Any]:
    args = Namespace(
        holdings_file=request.holdings_file,
        market=request.market,
        symbols=request.symbols,
        limit=request.limit,
        reports_root=request.reports_root,
        publish_root=request.publish_root,
        snapshot_stamp=request.snapshot_stamp,
        latest_only=request.latest_only,
        skip_regenerate=request.skip_regenerate,
        skip_build=request.skip_build,
        skip_upload=request.skip_upload,
        skip_gen_base=request.skip_gen_base,
        skip_gen_fund=request.skip_gen_fund,
        fail_on_holding_error=request.fail_on_holding_error,
        parallelism=request.parallelism,
        pending_reverse_mode=request.pending_reverse_mode,
        day_bars=request.day_bars,
        m60_bars=request.m60_bars,
        m30_bars=request.m30_bars,
        m15_bars=request.m15_bars,
        m5_bars=request.m5_bars,
        zhongshu_level=request.zhongshu_level,
        tech_timeframes=tuple(_dedupe_timeframes(request.tech_timeframes)),
        publish_timeframes=tuple(_dedupe_timeframes(request.publish_timeframes)) if request.publish_timeframes else None,
        cloud_prefix=request.cloud_prefix,
        env_id=request.env_id,
        region=request.region,
        api_key=request.api_key,
        api_key_name=request.api_key_name,
        api_key_expire_in=request.api_key_expire_in,
        delete_created_api_key=request.delete_created_api_key,
        upload_dry_run=request.upload_dry_run,
    )
    regeneration_result: dict[str, Any] | None = None
    if not args.skip_regenerate:
        regeneration_result = regenerate_holdings(args)
    result = _publish_build_and_upload(args)
    result["regenerated"] = not args.skip_regenerate
    result["generated_timeframes"] = list(args.tech_timeframes)
    if regeneration_result is not None:
        result["regeneration_summary"] = regeneration_result
    return result


def _run_technical_refresh(request: TechnicalRefreshRequest) -> dict[str, Any]:
    publish_timeframes = _normalize_technical_publish_timeframes(request.publish_timeframes)
    with _filtered_holdings_file(
        holdings_file=Path(request.holdings_file),
        market=request.market,
        symbols=request.symbols,
        limit=request.limit,
    ) as filtered:
        filtered_holdings_path, holdings = filtered
        prepare_result = run_batch_prepare(
            holdings_path=filtered_holdings_path,
            day_start=request.day_start,
            day_bars=request.day_bars,
            m60_start=request.m60_start,
            m60_bars=request.m60_bars,
            m30_start=request.m30_start,
            m30_bars=request.m30_bars,
            m15_start=request.m15_start,
            m15_bars=request.m15_bars,
            m5_start=request.m5_start,
            m5_bars=request.m5_bars,
            pending_reverse_mode=request.pending_reverse_mode,
            zhongshu_level=request.zhongshu_level,
            timeframes=tuple(_dedupe_timeframes(request.tech_timeframes)),
        )
        publish_args = _build_publish_namespace(
            holdings_file=request.holdings_file,
            reports_root=request.reports_root,
            publish_root=request.publish_root,
            snapshot_stamp=request.snapshot_stamp,
            latest_only=request.latest_only,
            skip_build=request.skip_build,
            skip_upload=request.skip_upload,
            publish_timeframes=publish_timeframes,
            cloud_prefix=request.cloud_prefix,
            env_id=request.env_id,
            region=request.region,
            api_key=request.api_key,
            api_key_name=request.api_key_name,
            api_key_expire_in=request.api_key_expire_in,
            delete_created_api_key=request.delete_created_api_key,
            upload_dry_run=request.upload_dry_run,
        )
        publish_result = _publish_build_and_upload(publish_args)
    publish_result.update(
        {
            "security_count": prepare_result.security_count,
            "symbols": [item.symbol for item in holdings],
            "generated_timeframes": list(prepare_result.selected_timeframes),
            "manifest_path": str(prepare_result.manifest_path),
            "summary_path": str(prepare_result.summary_path) if prepare_result.summary_path else None,
        }
    )
    return publish_result


def _serialize_job(job: _JobRecord) -> JobStateResponse:
    return JobStateResponse(
        job_id=job.job_id,
        kind=job.kind,
        status=job.status,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        request=job.request,
        result=job.result,
        error=job.error,
    )


def _run_job(job_id: str, kind: JobKind) -> None:
    job = JOBS.get(job_id)
    if job is None:
        return
    JOBS.update(job_id, status="running", started_at=_now_iso(), error=None)
    try:
        if kind == "publish_refresh":
            payload = PublishRefreshRequest.model_validate(job.request)
            result = _run_publish_refresh(payload)
        else:
            payload = TechnicalRefreshRequest.model_validate(job.request)
            result = _run_technical_refresh(payload)
        JOBS.update(job_id, status="succeeded", finished_at=_now_iso(), result=result)
    except Exception:
        JOBS.update(job_id, status="failed", finished_at=_now_iso(), error=traceback.format_exc())


app = FastAPI(
    title="Chanlun Stock Service",
    version="0.1.0",
    summary="Container-friendly API for holdings analysis refresh and CloudBase publish.",
)
JOBS = _JobStore()
EXECUTOR = ThreadPoolExecutor(max_workers=max(1, int(os.environ.get("CHANLUN_API_MAX_WORKERS", "2"))))


@app.get("/healthz")
def healthz() -> dict[str, Any]:
    return {
        "status": "ok",
        "time": _now_iso(),
        "root": str(ROOT),
        "holdings_file": str(HOLDINGS_FILE),
    }


@app.post("/jobs/publish-refresh", response_model=JobCreatedResponse)
def submit_publish_refresh(request: PublishRefreshRequest) -> JobCreatedResponse:
    job = JOBS.create("publish_refresh", request.model_dump())
    EXECUTOR.submit(_run_job, job.job_id, job.kind)
    return JobCreatedResponse(job_id=job.job_id, kind=job.kind, status=job.status, created_at=job.created_at)


@app.post("/jobs/technical-refresh", response_model=JobCreatedResponse)
def submit_technical_refresh(request: TechnicalRefreshRequest) -> JobCreatedResponse:
    job = JOBS.create("technical_refresh", request.model_dump())
    EXECUTOR.submit(_run_job, job.job_id, job.kind)
    return JobCreatedResponse(job_id=job.job_id, kind=job.kind, status=job.status, created_at=job.created_at)


@app.get("/jobs/{job_id}", response_model=JobStateResponse)
def get_job(job_id: str) -> JobStateResponse:
    job = JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown job_id: {job_id}")
    return _serialize_job(job)


@app.get("/jobs", response_model=list[JobStateResponse])
def list_jobs() -> list[JobStateResponse]:
    return [_serialize_job(job) for job in JOBS.list()]