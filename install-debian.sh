#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "This installer must be run as root on Debian/Ubuntu/Kali to install system dependencies." >&2
    echo "Restart it with: sudo bash install-debian.sh" >&2
    exit 1
fi

if command -v apt-get >/dev/null 2>&1; then
    apt-get update
    apt-get install -y python3 python3-venv python3-pip git nmap
else
    echo "apt-get was not found. This installer is intended for Debian/Ubuntu/Kali systems." >&2
    exit 1
fi

if command -v nmap >/dev/null 2>&1; then
    echo "Nmap found: $(command -v nmap)"
else
    echo "Error: nmap was not installed or is not available in PATH." >&2
    exit 1
fi

PYTHON_BIN="${PYTHON_BIN:-python3}"
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

echo "Installation complete. Run: source .venv/bin/activate && python cli.py"
