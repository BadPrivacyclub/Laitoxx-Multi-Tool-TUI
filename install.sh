#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -n "${PREFIX:-}" ] && command -v pkg >/dev/null 2>&1; then
    exec bash install-termux.sh
fi

if command -v apt-get >/dev/null 2>&1; then
    exec bash install-debian.sh
fi

if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
else
    echo "Python 3.13+ is required but was not found in PATH." >&2
    exit 1
fi

echo "Using: $($PYTHON_BIN --version)"

if [ ! -d ".venv" ]; then
    "$PYTHON_BIN" -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

INSTALL_GEOCLIP="${LAITOXX_INSTALL_PLANET:-${LAITOXX_INSTALL_GEOCLIP:-}}"
if [ -z "$INSTALL_GEOCLIP" ] && [ -t 0 ]; then
    read -r -p "Install optional PlaNet-like/GeoCLIP Photo Geolocation mode? [y/N] " INSTALL_GEOCLIP
fi
if [[ "${INSTALL_GEOCLIP,,}" == "y" ]]; then
    echo "Installing optional PlaNet-like/GeoCLIP dependencies..."
    python -m pip install -r requirements-photo2geo-geoclip.txt
fi

if command -v nmap >/dev/null 2>&1; then
    echo "Nmap found: $(command -v nmap)"
else
    echo "Warning: nmap was not found in PATH. Install it to use the Nmap tool."
    echo "Examples: sudo apt install nmap | pkg install nmap | brew install nmap"
fi

echo "Installation complete. Run: source .venv/bin/activate && python cli.py"
