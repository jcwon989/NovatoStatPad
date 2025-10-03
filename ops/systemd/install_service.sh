#!/usr/bin/env bash
set -euo pipefail

# Install and enable a systemd service for the Novato StatPad scoreboard app.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SERVICE_NAME="novato-statpad.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"

USER_NAME="${SUDO_USER:-$(whoami)}"
GROUP_NAME="${USER_NAME}"

PYTHON_BIN="python3"
VENV_DIR="${APP_DIR}/.venv"
PIP_BIN="${VENV_DIR}/bin/pip"
PY_BIN="${VENV_DIR}/bin/python"

LOG_DIR="${APP_DIR}/logs"
RUN_SCRIPT="${APP_DIR}/ops/systemd/run_scoreboard.sh"

echo "[1/6] Ensure required system packages are installed"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update -y
  sudo apt-get install -y python3-venv python3-pip
fi

echo "[2/6] Create virtual environment and install dependencies"
if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi
"${PIP_BIN}" install --upgrade pip
if [[ -f "${APP_DIR}/requirements.txt" ]]; then
  "${PIP_BIN}" install -r "${APP_DIR}/requirements.txt"
fi

echo "[3/6] Prepare logs and scripts permissions"
mkdir -p "${LOG_DIR}"
chmod 755 "${RUN_SCRIPT}"

echo "[4/6] Write systemd unit: ${SERVICE_PATH}"
sudo bash -c "cat > '${SERVICE_PATH}'" <<EOF
[Unit]
Description=Novato StatPad Scoreboard
After=network-online.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=${USER_NAME}
Group=${GROUP_NAME}
WorkingDirectory=${APP_DIR}
ExecStart=${RUN_SCRIPT}
Restart=always
RestartSec=3
StandardOutput=append:${LOG_DIR}/stdout.log
StandardError=append:${LOG_DIR}/stderr.log
# EnvironmentFile=${APP_DIR}/.env

[Install]
WantedBy=multi-user.target
EOF

echo "[5/6] Enable and start service"
sudo systemctl daemon-reload
sudo systemctl enable "${SERVICE_NAME}"
sudo systemctl restart "${SERVICE_NAME}"

echo "[6/6] Done"
echo "Service:   ${SERVICE_NAME}"
echo "Status:    sudo systemctl status ${SERVICE_NAME}"
echo "Logs:      tail -f ${LOG_DIR}/stdout.log ${LOG_DIR}/stderr.log"
echo "Disable:   sudo systemctl disable --now ${SERVICE_NAME}"


