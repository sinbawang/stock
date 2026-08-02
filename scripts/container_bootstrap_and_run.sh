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
KLINE_SYNC_BACKUP_ON_START="${KLINE_SYNC_BACKUP_ON_START:-false}"
KLINE_SYNC_BACKUP_INTERVAL_SECONDS="${KLINE_SYNC_BACKUP_INTERVAL_SECONDS:-1800}"
KLINE_SYNC_BACKUP_ON_STOP="${KLINE_SYNC_BACKUP_ON_STOP:-true}"

mkdir -p "${KLINE_SYNC_LOCAL_ROOT}"
mkdir -p "$(dirname "${KLINE_SYNC_MANIFEST_PATH}")"

backup_loop_pid=""
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
  python /app/scripts/sync_kline_cache_cloudbase.py restore \
    --target-dir "${KLINE_SYNC_LOCAL_ROOT}" \
    --cloud-prefix "${KLINE_SYNC_CLOUD_PREFIX}" \
    --manifest-path "${KLINE_SYNC_MANIFEST_PATH}" \
    --pointer-path "${KLINE_SYNC_POINTER_PATH}" \
    --fetch-manifest \
    --no-use-cli-download
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

log "starting main process: $*"
trap 'handle_shutdown' TERM INT
"$@" &
child_pid=$!
wait "${child_pid}"
child_status=$?
exit "${child_status}"
