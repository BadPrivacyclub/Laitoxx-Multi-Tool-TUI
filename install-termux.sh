#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ -z "${PREFIX:-}" ] || [ ! -d "$PREFIX" ] || ! command -v pkg >/dev/null 2>&1; then
    echo "This installer is intended for native Termux. Use install-debian.sh inside proot Debian/Ubuntu." >&2
    exit 1
fi

pkg update
pkg install -y python git nmap clang make pkg-config rust libjpeg-turbo libpng openblas

if command -v nmap >/dev/null 2>&1; then
    echo "Nmap found: $(command -v nmap)"
else
    echo "Error: nmap was not installed or is not available in PATH." >&2
    exit 1
fi

TORCH_MODE="${PHOTO2GEO_TORCH:-}"
if [ -z "$TORCH_MODE" ] && [ -t 0 ]; then
    echo "PyTorch is optional and only needed for Netryx indexing or GeoCLIP inference."
    echo "Choose: none, tur, proot"
    read -r -p "PyTorch setup for Termux [none]: " TORCH_MODE
fi
TORCH_MODE="${TORCH_MODE:-none}"

VENV_ARGS=()
case "$TORCH_MODE" in
    tur)
        pkg install -y tur-repo
        pkg update
        pkg install -y python-torch python-torchvision
        VENV_ARGS=(--system-site-packages)
        ;;
    proot)
        pkg install -y proot-distro
        echo "Installed proot-distro. Recommended Photo Geolocation AI setup:"
        echo "  proot-distro install ubuntu"
        echo "  proot-distro login ubuntu"
        echo "  apt update && apt install -y python3 python3-pip python3-venv git nmap"
        echo "  bash install-debian.sh"
        ;;
    none|"")
        ;;
    *)
        echo "Unknown PHOTO2GEO_TORCH value: $TORCH_MODE" >&2
        exit 1
        ;;
esac

if [ ! -d ".venv" ]; then
    python -m venv "${VENV_ARGS[@]}" .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-termux.txt

INSTALL_GEOCLIP="${LAITOXX_INSTALL_PLANET:-${LAITOXX_INSTALL_GEOCLIP:-}}"
if [ -z "$INSTALL_GEOCLIP" ] && [ -t 0 ]; then
    read -r -p "Install optional PlaNet-like/GeoCLIP package? Requires working PyTorch. [y/N] " INSTALL_GEOCLIP
fi
if [[ "${INSTALL_GEOCLIP,,}" == "y" ]]; then
    echo "Installing optional PlaNet-like/GeoCLIP dependencies..."
    python -m pip install -r requirements-photo2geo-geoclip.txt
fi

echo "Installation complete. Run: source .venv/bin/activate && python cli.py"
