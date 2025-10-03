#!/usr/bin/env bash
set -euo pipefail

# This script launches the scoreboard app using the project's virtual environment.
# It is intended to be called by a systemd unit.

# Resolve script directory and project root (ops/systemd -> project root is two levels up)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

VENV_DIR="${APP_DIR}/.venv"
PY_BIN="${VENV_DIR}/bin/python"

if [[ ! -x "${PY_BIN}" ]]; then
  echo "[run_scoreboard] Virtualenv python not found: ${PY_BIN}" >&2
  echo "[run_scoreboard] Create venv first (see ops/systemd/install_service.sh)." >&2
  exit 1
fi

cd "${APP_DIR}"

# Optional environment variables for Raspberry Pi environments
# export SDL_AUDIODRIVER=alsa
# export SDL_VIDEODRIVER=fbcon

exec "${PY_BIN}" "${APP_DIR}/scoreboard.py"


