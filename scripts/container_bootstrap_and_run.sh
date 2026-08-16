#!/bin/sh
set -eu

log() {
  printf '%s %s\n' "[kline-sync]" "$*"
}

is_true() {
  case "${1:-}" in
    1|true|TRUE|True|yes|YES|on|ON) return 0 ;;
    *) return 1 ;;
  esac
}

KLINE_SYNC_ENABLED="${KLINE_SYNC_ENABLED:-true}"
KLINE_SYNC_CLOUD_PREFIX="${KLINE_SYNC_CLOUD_PREFIX:-stock-kline-cache/latest}"
KLINE_SYNC_LOCAL_ROOT="${STOCK_LOCAL_STORE_ROOT:-/data/stock-kline-cache}"
KLINE_SYNC_MANIFEST_PATH="${KLINE_SYNC_MANIFEST_PATH:-/tmp/stock-kline-cache/cloudbase-upload-manifest.json}"
KLINE_SYNC_POINTER_PATH="${KLINE_SYNC_POINTER_PATH:-/tmp/stock-kline-cache/manifest-pointer.json}"
KLINE_SYNC_RESTORE_ON_START="${KLINE_SYNC_RESTORE_ON_START:-false}"
KLINE_SYNC_RESTORE_STRICT="${KLINE_SYNC_RESTORE_STRICT:-false}"
KLINE_SYNC_RESTORE_FILE_ID="${KLINE_SYNC_RESTORE_FILE_ID:-}"
KLINE_SYNC_BACKUP_ON_START="${KLINE_SYNC_BACKUP_ON_START:-false}"
KLINE_SYNC_BACKUP_INTERVAL_SECONDS="${KLINE_SYNC_BACKUP_INTERVAL_SECONDS:-1800}"
KLINE_SYNC_BACKUP_ON_STOP="${KLINE_SYNC_BACKUP_ON_STOP:-true}"
INTRADAY_SCHEDULER_ENABLED="${INTRADAY_SCHEDULER_ENABLED:-false}"
INTRADAY_SCHEDULER_TIMEZONE="${INTRADAY_SCHEDULER_TIMEZONE:-Asia/Shanghai}"
INTRADAY_SCHEDULER_GRACE_SECONDS="${INTRADAY_SCHEDULER_GRACE_SECONDS:-150}"
INTRADAY_SCHEDULER_POLL_SECONDS="${INTRADAY_SCHEDULER_POLL_SECONDS:-30}"
M5_INTRADAY_SCHEDULER_ENABLED="${M5_INTRADAY_SCHEDULER_ENABLED:-false}"
EOD_SCHEDULER_ENABLED="${EOD_SCHEDULER_ENABLED:-false}"
EOD_SCHEDULER_TIMEZONE="${EOD_SCHEDULER_TIMEZONE:-Asia/Shanghai}"
EOD_SCHEDULER_GRACE_SECONDS="${EOD_SCHEDULER_GRACE_SECONDS:-300}"
EOD_SCHEDULER_POLL_SECONDS="${EOD_SCHEDULER_POLL_SECONDS:-30}"

mkdir -p "${KLINE_SYNC_LOCAL_ROOT}"
mkdir -p "$(dirname "${KLINE_SYNC_MANIFEST_PATH}")"

backup_loop_pid=""
scheduler_pid=""
mini_scheduler_pid=""
eod_scheduler_pid=""
child_pid=""

run_backup_once() {
  log "running backup to ${KLINE_SYNC_CLOUD_PREFIX}"
  python /app/scripts/sync_kline_cache_cloudbase.py backup \
    --source-dir "${KLINE_SYNC_LOCAL_ROOT}" \
    --cloud-prefix "${KLINE_SYNC_CLOUD_PREFIX}" \
    --manifest-path "${KLINE_SYNC_MANIFEST_PATH}" \
    --pointer-path "${KLINE_SYNC_POINTER_PATH}"
}

run_restore_once() {
  log "running restore from ${KLINE_SYNC_CLOUD_PREFIX}"
  if [ -n "${KLINE_SYNC_RESTORE_FILE_ID}" ]; then
    log "using explicit restore file id"
    python /app/scripts/sync_kline_cache_cloudbase.py restore \
      --target-dir "${KLINE_SYNC_LOCAL_ROOT}" \
      --cloud-prefix "${KLINE_SYNC_CLOUD_PREFIX}" \
      --manifest-path "${KLINE_SYNC_MANIFEST_PATH}" \
      --pointer-path "${KLINE_SYNC_POINTER_PATH}" \
      --manifest-file-id "${KLINE_SYNC_RESTORE_FILE_ID}" \
      --no-use-cli-download
  else
    python /app/scripts/sync_kline_cache_cloudbase.py restore \
      --target-dir "${KLINE_SYNC_LOCAL_ROOT}" \
      --cloud-prefix "${KLINE_SYNC_CLOUD_PREFIX}" \
      --manifest-path "${KLINE_SYNC_MANIFEST_PATH}" \
      --pointer-path "${KLINE_SYNC_POINTER_PATH}" \
      --fetch-manifest \
      --no-use-cli-download
  fi
}

start_backup_loop() {
  interval="$1"
  (
    while true; do
      sleep "${interval}"
      if ! run_backup_once; then
        log "backup loop iteration failed"
      fi
    done
  ) &
  backup_loop_pid=$!
  log "started periodic backup loop (interval=${interval}s)"
}

start_intraday_scheduler() {
  INTRADAY_SCHEDULER_TIMEZONE="${INTRADAY_SCHEDULER_TIMEZONE}" \
  INTRADAY_SCHEDULER_GRACE_SECONDS="${INTRADAY_SCHEDULER_GRACE_SECONDS}" \
  INTRADAY_SCHEDULER_POLL_SECONDS="${INTRADAY_SCHEDULER_POLL_SECONDS}" \
  python /app/scripts/run_m30_intraday_scheduler.py &
  scheduler_pid=$!
  log "started intraday scheduler (timezone=${INTRADAY_SCHEDULER_TIMEZONE})"
}

start_m5_intraday_scheduler() {
  INTRADAY_SCHEDULER_TIMEZONE="${INTRADAY_SCHEDULER_TIMEZONE}" \
  INTRADAY_SCHEDULER_GRACE_SECONDS="${INTRADAY_SCHEDULER_GRACE_SECONDS}" \
  INTRADAY_SCHEDULER_POLL_SECONDS="${INTRADAY_SCHEDULER_POLL_SECONDS}" \
  python /app/scripts/run_m30_intraday_scheduler.py --profile m5_intraday &
  mini_scheduler_pid=$!
  log "started m5 intraday scheduler (timezone=${INTRADAY_SCHEDULER_TIMEZONE})"
}

start_eod_scheduler() {
  INTRADAY_SCHEDULER_TIMEZONE="${EOD_SCHEDULER_TIMEZONE}" \
  INTRADAY_SCHEDULER_GRACE_SECONDS="${EOD_SCHEDULER_GRACE_SECONDS}" \
  INTRADAY_SCHEDULER_POLL_SECONDS="${EOD_SCHEDULER_POLL_SECONDS}" \
  python /app/scripts/run_m30_intraday_scheduler.py --profile eod &
  eod_scheduler_pid=$!
  log "started eod scheduler (timezone=${EOD_SCHEDULER_TIMEZONE})"
}

handle_shutdown() {
  if is_true "${KLINE_SYNC_ENABLED}" && is_true "${KLINE_SYNC_BACKUP_ON_STOP}"; then
    log "received shutdown signal; running final backup"
    if ! run_backup_once; then
      log "final backup failed"
    fi
  fi

  if [ -n "${backup_loop_pid}" ] && kill -0 "${backup_loop_pid}" 2>/dev/null; then
    kill "${backup_loop_pid}" 2>/dev/null || true
    wait "${backup_loop_pid}" 2>/dev/null || true
  fi

  if [ -n "${scheduler_pid}" ] && kill -0 "${scheduler_pid}" 2>/dev/null; then
    kill "${scheduler_pid}" 2>/dev/null || true
    wait "${scheduler_pid}" 2>/dev/null || true
  fi

  if [ -n "${mini_scheduler_pid}" ] && kill -0 "${mini_scheduler_pid}" 2>/dev/null; then
    kill "${mini_scheduler_pid}" 2>/dev/null || true
    wait "${mini_scheduler_pid}" 2>/dev/null || true
  fi

  if [ -n "${eod_scheduler_pid}" ] && kill -0 "${eod_scheduler_pid}" 2>/dev/null; then
    kill "${eod_scheduler_pid}" 2>/dev/null || true
    wait "${eod_scheduler_pid}" 2>/dev/null || true
  fi

  if [ -n "${child_pid}" ] && kill -0 "${child_pid}" 2>/dev/null; then
    kill "${child_pid}" 2>/dev/null || true
    wait "${child_pid}" 2>/dev/null || true
  fi

  exit 0
}

if is_true "${KLINE_SYNC_ENABLED}"; then
  log "sync enabled"

  if is_true "${KLINE_SYNC_RESTORE_ON_START}"; then
    if ! run_restore_once; then
      if is_true "${KLINE_SYNC_RESTORE_STRICT}"; then
        log "restore failed and strict mode is enabled; exiting"
        exit 1
      fi
      log "restore failed; continuing startup"
    fi
  fi

  if is_true "${KLINE_SYNC_BACKUP_ON_START}"; then
    if ! run_backup_once; then
      log "startup backup failed; continuing startup"
    fi
  fi

  case "${KLINE_SYNC_BACKUP_INTERVAL_SECONDS}" in
    ''|0)
      log "periodic backup disabled"
      ;;
    *)
      start_backup_loop "${KLINE_SYNC_BACKUP_INTERVAL_SECONDS}"
      ;;
  esac
else
  log "sync disabled"
fi

if is_true "${INTRADAY_SCHEDULER_ENABLED}"; then
  start_intraday_scheduler
else
  log "intraday scheduler disabled"
fi

if is_true "${M5_INTRADAY_SCHEDULER_ENABLED}"; then
  start_m5_intraday_scheduler
else
  log "m5 intraday scheduler disabled"
fi

if is_true "${EOD_SCHEDULER_ENABLED}"; then
  start_eod_scheduler
else
  log "eod scheduler disabled"
fi

log "starting main process: $*"
trap 'handle_shutdown' TERM INT
"$@" &
child_pid=$!
wait "${child_pid}"
child_status=$?
exit "${child_status}"
