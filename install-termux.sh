#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

if [ -z "${PREFIX:-}" ] || [ ! -d "${PREFIX:-}" ] || ! command -v pkg >/dev/null 2>&1; then
    echo "This installer is for native Termux. Use install-debian.sh inside proot." >&2
    exit 1
fi

# Try to install a package, skip silently if unavailable
pkg_try() {
    for _pkg in "$@"; do
        if pkg install -y "$_pkg" >/dev/null 2>&1; then
            echo "  [ok] $_pkg"
        else
            echo "  [skip] $_pkg (not in repository)"
        fi
    done
}

echo "==> Updating package lists..."
pkg update -y

echo "==> Installing Python and git..."
pkg install -y python git

echo "==> Installing build tools..."
pkg_try clang make cmake pkg-config binutils autoconf automake

echo "==> Installing Rust (needed by some pip packages)..."
pkg_try rust

echo "==> Installing native libraries..."
pkg_try libjpeg-turbo libpng openblas freetype libwebp libffi openssl

echo "==> Installing nmap..."
pkg_try nmap

echo "==> Installing pre-built Python scientific packages (faster than pip builds)..."
pkg_try python-numpy python-cryptography

# Termux ships a patched pip — do NOT run pip install --upgrade pip
# Use pip directly from the venv without upgrading
TORCH_MODE="${PHOTO2GEO_TORCH:-}"
if [ -z "$TORCH_MODE" ] && [ -t 0 ]; then
    echo ""
    echo "PyTorch is optional (only needed for Netryx indexing or GeoCLIP)."
    echo "Options:"
    echo "  none  — skip, core tools work without it"
    echo "  tur   — install from Termux User Repository (native, recommended)"
    echo "  proot — install proot-distro and use Debian/Ubuntu environment"
    read -r -p "PyTorch setup [none]: " TORCH_MODE
fi
TORCH_MODE="${TORCH_MODE:-none}"

VENV_FLAGS=""
case "$TORCH_MODE" in
    tur)
        echo "==> Installing PyTorch via TUR..."
        pkg_try tur-repo
        pkg update -y
        pkg_try python-torch python-torchvision python-torchaudio
        VENV_FLAGS="--system-site-packages"
        ;;
    proot)
        echo "==> Installing proot-distro..."
        pkg_try proot-distro
        echo ""
        echo "proot-distro installed. To continue with a full Debian environment:"
        echo "  proot-distro install ubuntu"
        echo "  proot-distro login ubuntu"
        echo "  apt update && apt install -y python3 python3-pip python3-venv git nmap"
        echo "  bash install-debian.sh"
        echo ""
        echo "Continuing with native Termux setup (without PyTorch)..."
        ;;
    none|"")
        ;;
    *)
        echo "Unknown PHOTO2GEO_TORCH value: $TORCH_MODE" >&2
        exit 1
        ;;
esac

echo "==> Creating virtual environment..."
if [ ! -d ".venv" ]; then
    # shellcheck disable=SC2086
    python -m venv $VENV_FLAGS .venv
fi

. .venv/bin/activate

echo "==> Installing Python dependencies..."
# Skip pip upgrade — Termux ships a patched pip, upgrading breaks it
python -m pip install --no-build-isolation -r requirements-termux.txt

INSTALL_GEOCLIP="${LAITOXX_INSTALL_PLANET:-${LAITOXX_INSTALL_GEOCLIP:-}}"
if [ -z "$INSTALL_GEOCLIP" ] && [ -t 0 ]; then
    read -r -p "Install optional GeoCLIP package? Requires working PyTorch. [y/N] " INSTALL_GEOCLIP
fi
case "$(printf '%s' "${INSTALL_GEOCLIP:-}" | tr '[:upper:]' '[:lower:]')" in
    y|yes)
        echo "Installing optional GeoCLIP dependencies..."
        python -m pip install --no-build-isolation -r requirements-photo2geo-geoclip.txt
        ;;
esac

echo ""
echo "Done. Run:"
echo "  source .venv/bin/activate"
echo "  python cli.py"
