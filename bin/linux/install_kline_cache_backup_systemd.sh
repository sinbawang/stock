#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SYSTEMD_SRC_DIR="${ROOT_DIR}/bin/linux/systemd"
SYSTEMD_TARGET_DIR="/etc/systemd/system"
ENV_FILE_PATH="/etc/default/stock-kline-cache"

SERVICE_USER="${SERVICE_USER:-ubuntu}"
WORKING_DIR="${WORKING_DIR:-/opt/stock}"
CLOUD_PREFIX="${CLOUD_PREFIX:-stock-kline-cache/latest}"
MANIFEST_PATH="${MANIFEST_PATH:-/opt/stock/build/stock-kline-cache/cloudbase-upload-manifest.json}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "ERROR: please run as root (sudo)." >&2
  exit 1
fi

if [[ ! -d "${SYSTEMD_SRC_DIR}" ]]; then
  echo "ERROR: missing systemd template dir: ${SYSTEMD_SRC_DIR}" >&2
  exit 1
fi

if [[ ! -d "${SYSTEMD_TARGET_DIR}" ]]; then
  echo "ERROR: missing systemd target dir: ${SYSTEMD_TARGET_DIR}" >&2
  exit 1
fi

cp "${SYSTEMD_SRC_DIR}/stock-kline-cache-backup.service" "${SYSTEMD_TARGET_DIR}/"
cp "${SYSTEMD_SRC_DIR}/stock-kline-cache-backup.timer" "${SYSTEMD_TARGET_DIR}/"
cp "${SYSTEMD_SRC_DIR}/stock-kline-cache-shutdown-backup.service" "${SYSTEMD_TARGET_DIR}/"

# Replace defaults so templates work out-of-box on the target machine.
sed -i "s|User=ubuntu|User=${SERVICE_USER}|g" "${SYSTEMD_TARGET_DIR}/stock-kline-cache-backup.service"
sed -i "s|WorkingDirectory=/opt/stock|WorkingDirectory=${WORKING_DIR}|g" "${SYSTEMD_TARGET_DIR}/stock-kline-cache-backup.service"
sed -i "s|User=ubuntu|User=${SERVICE_USER}|g" "${SYSTEMD_TARGET_DIR}/stock-kline-cache-shutdown-backup.service"
sed -i "s|WorkingDirectory=/opt/stock|WorkingDirectory=${WORKING_DIR}|g" "${SYSTEMD_TARGET_DIR}/stock-kline-cache-shutdown-backup.service"

if [[ ! -f "${ENV_FILE_PATH}" ]]; then
  cat > "${ENV_FILE_PATH}" <<EOF
# CloudBase runtime settings for kline cache backup
# Optional: provide credentials via the runtime environment or Tencent secret variables.
CLOUDBASE_ENV_ID=
CLOUDBASE_REGION=ap-shanghai
CLOUD_PREFIX=${CLOUD_PREFIX}
MANIFEST_PATH=${MANIFEST_PATH}
EOF
  echo "created ${ENV_FILE_PATH}; please fill CLOUDBASE_ENV_ID and provide credentials via the runtime environment if needed"
else
  echo "found ${ENV_FILE_PATH}; keep existing values"
fi

systemctl daemon-reload
systemctl enable --now stock-kline-cache-backup.timer
systemctl enable stock-kline-cache-shutdown-backup.service

echo ""
echo "Install finished. Next commands:"
echo "  systemctl status stock-kline-cache-backup.timer --no-pager"
echo "  systemctl start stock-kline-cache-backup.service"
echo "  journalctl -u stock-kline-cache-backup.service -n 200 --no-pager"
