#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

if [ -z "${PREFIX:-}" ] || [ ! -d "${PREFIX:-}" ] || ! command -v pkg >/dev/null 2>&1; then
    echo "This installer is for native Termux. Use install-debian.sh inside proot." >&2
    exit 1
fi

pkg update
pkg install -y python git nmap clang make pkg-config rust libjpeg-turbo libpng openblas

TORCH_MODE="${PHOTO2GEO_TORCH:-}"
if [ -z "$TORCH_MODE" ] && [ -t 0 ]; then
    echo "PyTorch is optional (needed for Netryx indexing or GeoCLIP)."
    echo "Options: none, tur, proot"
    read -r -p "PyTorch setup [none]: " TORCH_MODE
fi
TORCH_MODE="${TORCH_MODE:-none}"

VENV_FLAGS=""
case "$TORCH_MODE" in
    tur)
        pkg install -y tur-repo
        pkg update
        pkg install -y python-torch python-torchvision
        VENV_FLAGS="--system-site-packages"
        ;;
    proot)
        pkg install -y proot-distro
        echo "proot-distro installed. Recommended next steps:"
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
    # shellcheck disable=SC2086
    python -m venv $VENV_FLAGS .venv
fi

. .venv/bin/activate

python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements-termux.txt

INSTALL_GEOCLIP="${LAITOXX_INSTALL_PLANET:-${LAITOXX_INSTALL_GEOCLIP:-}}"
if [ -z "$INSTALL_GEOCLIP" ] && [ -t 0 ]; then
    read -r -p "Install optional GeoCLIP package? Requires working PyTorch. [y/N] " INSTALL_GEOCLIP
fi
case "$(printf '%s' "${INSTALL_GEOCLIP:-}" | tr '[:upper:]' '[:lower:]')" in
    y|yes)
        echo "Installing optional GeoCLIP dependencies..."
        python -m pip install -r requirements-photo2geo-geoclip.txt
        ;;
esac

echo "Done. Run: source .venv/bin/activate && python cli.py"
