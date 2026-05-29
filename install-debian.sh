#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root to install system packages: sudo bash install-debian.sh" >&2
    exit 1
fi

if ! command -v apt-get >/dev/null 2>&1; then
    echo "apt-get not found. This installer is for Debian/Ubuntu/Kali." >&2
    exit 1
fi

apt-get update
apt-get install -y python3 python3-venv python3-pip git nmap

PYTHON_BIN="${PYTHON_BIN:-python3}"
echo "Using: $($PYTHON_BIN --version)"

if [ ! -d ".venv" ]; then
    "$PYTHON_BIN" -m venv .venv
fi

. .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt

INSTALL_GEOCLIP="${LAITOXX_INSTALL_PLANET:-${LAITOXX_INSTALL_GEOCLIP:-}}"
if [ -z "$INSTALL_GEOCLIP" ] && [ -t 0 ]; then
    read -r -p "Install optional GeoCLIP Photo Geolocation mode? [y/N] " INSTALL_GEOCLIP
fi
case "$(printf '%s' "${INSTALL_GEOCLIP:-}" | tr '[:upper:]' '[:lower:]')" in
    y|yes)
        echo "Installing optional GeoCLIP dependencies..."
        python -m pip install -r requirements-photo2geo-geoclip.txt
        ;;
esac

echo "Done. Run: source .venv/bin/activate && python cli.py"
