#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

if [ -z "${PREFIX:-}" ] || [ ! -d "${PREFIX:-}" ] || ! command -v pkg >/dev/null 2>&1; then
    echo "This installer is for native Termux. Use install-debian.sh inside proot." >&2
    exit 1
fi

# Install a pkg package, skip if unavailable
pkg_try() {
    for _pkg in "$@"; do
        if pkg install -y "$_pkg" >/dev/null 2>&1; then
            echo "  [ok] $_pkg"
        else
            echo "  [skip] $_pkg (not in repository)"
        fi
    done
}

# Install a pip package one at a time; skip on failure so one broken package
# does not abort the whole install (e.g. lupa needing Lua headers)
pip_try() {
    for _pkg in "$@"; do
        if python -m pip install --prefer-binary --no-build-isolation "$_pkg" >/dev/null 2>&1; then
            echo "  [ok] $_pkg"
        else
            echo "  [skip] $_pkg (build failed — install manually if needed)"
        fi
    done
}

echo "==> Updating package lists..."
pkg update -y

echo "==> Installing Python and git..."
pkg install -y python git

echo "==> Installing build tools..."
pkg_try clang make cmake pkg-config binutils autoconf automake meson ninja

echo "==> Installing Rust (needed by some pip packages)..."
pkg_try rust

echo "==> Installing native libraries..."
pkg_try libjpeg-turbo libpng openblas freetype libwebp libffi openssl

# lua54 is needed to build lupa (Python-Lua bridge used by plugin system)
echo "==> Installing Lua (required for plugin system)..."
pkg_try lua54 lua53 lua52

echo "==> Installing nmap..."
pkg_try nmap

echo "==> Installing pre-built Python packages via pkg (avoids pip source builds)..."
pkg_try python-numpy python-cryptography python-pillow

TORCH_MODE="${PHOTO2GEO_TORCH:-}"
if [ -z "$TORCH_MODE" ] && [ -t 0 ]; then
    echo ""
    echo "PyTorch is optional (only needed for Netryx indexing or GeoCLIP)."
    echo "Options:"
    echo "  none  — skip, core tools work without it"
    echo "  tur   — install from Termux User Repository (native, recommended)"
    echo "  proot — use proot-distro with Debian/Ubuntu environment"
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
        pkg_try proot-distro
        echo ""
        echo "proot-distro installed. Recommended next steps:"
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

# Core pure-Python packages — install first, guaranteed to work
echo "==> Installing core dependencies (one by one to survive build failures)..."
pip_try \
    "textual>=0.80" \
    "rich>=13.0" \
    "InquirerPy>=0.3" \
    "prompt_toolkit>=3.0" \
    "requests" \
    "aiohttp" \
    "aiohttp-socks" \
    "PySocks" \
    "beautifulsoup4" \
    "colorama" \
    "phonenumbers" \
    "python-whois" \
    "hashid" \
    "pystyle"

# Native / heavier packages — may fail on some setups, non-fatal
echo "==> Installing optional/native dependencies..."
pip_try \
    "Pillow" \
    "lupa" \
    "paketlib" \
    "huggingface-hub" \
    "safetensors"

INSTALL_GEOCLIP="${LAITOXX_INSTALL_PLANET:-${LAITOXX_INSTALL_GEOCLIP:-}}"
if [ -z "$INSTALL_GEOCLIP" ] && [ -t 0 ]; then
    read -r -p "Install optional GeoCLIP Photo Geolocation package? Requires PyTorch. [y/N] " INSTALL_GEOCLIP
fi
case "$(printf '%s' "${INSTALL_GEOCLIP:-}" | tr '[:upper:]' '[:lower:]')" in
    y|yes)
        echo "Installing optional GeoCLIP dependencies..."
        pip_try geoclip
        python -m pip install --prefer-binary --no-build-isolation \
            -r requirements-photo2geo-geoclip.txt 2>/dev/null || \
            echo "  [warn] Some GeoCLIP deps failed — check requirements-photo2geo-geoclip.txt"
        ;;
esac

echo ""
echo "Done. Run:"
echo "  source .venv/bin/activate"
echo "  python cli.py"
