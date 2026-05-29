#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

# Termux
if [ -n "${PREFIX:-}" ] && [ -d "${PREFIX:-}" ] && command -v pkg >/dev/null 2>&1; then
    exec bash install-termux.sh
fi

# Debian / Ubuntu / Kali
if command -v apt-get >/dev/null 2>&1; then
    exec bash install-debian.sh
fi

# Generic fallback
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

if command -v nmap >/dev/null 2>&1; then
    echo "Nmap found: $(command -v nmap)"
else
    echo "Warning: nmap not found. Install it to use the Nmap tool."
    echo "  Debian/Ubuntu/Kali: sudo apt install nmap"
    echo "  macOS:              brew install nmap"
    echo "  Termux:             pkg install nmap"
fi

echo "Done. Run: source .venv/bin/activate && python cli.py"
