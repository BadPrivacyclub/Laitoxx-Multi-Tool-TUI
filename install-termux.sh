#!/usr/bin/env bash
set -eu

cd "$(dirname "$0")"

if [ -z "${PREFIX:-}" ] || [ ! -d "${PREFIX:-}" ] || ! command -v pkg >/dev/null 2>&1; then
    echo "This installer is for native Termux. Use install-debian.sh inside proot." >&2
    exit 1
fi

PKG_FAILED=""
PIP_FAILED=""

pkg_try() {
    for _pkg in "$@"; do
        if pkg install -y "$_pkg" >/dev/null 2>&1; then
            echo "  [ok] $_pkg"
        else
            echo "  [skip] $_pkg"
            PKG_FAILED="$PKG_FAILED $_pkg"
        fi
    done
}

pip_try() {
    for _pkg in "$@"; do
        if python -m pip install --prefer-binary --no-build-isolation "$_pkg" >/dev/null 2>&1; then
            echo "  [ok] $_pkg"
        else
            echo "  [FAIL] $_pkg"
            PIP_FAILED="$PIP_FAILED $_pkg"
        fi
    done
}

echo "==> Updating package lists..."
pkg update -y

echo "==> Installing Python and git..."
pkg install -y python git

echo "==> Installing build tools..."
pkg_try clang make cmake pkg-config binutils autoconf automake meson ninja

echo "==> Installing Rust..."
pkg_try rust

echo "==> Installing native libraries..."
pkg_try libjpeg-turbo libpng openblas freetype libwebp libffi openssl

echo "==> Installing Lua (required for plugin system)..."
pkg_try lua54 lua53 lua52

echo "==> Installing nmap..."
pkg_try nmap

echo "==> Installing pre-built Python packages via pkg..."
pkg_try python-numpy python-cryptography python-pillow

TORCH_MODE="${PHOTO2GEO_TORCH:-}"
if [ -z "$TORCH_MODE" ] && [ -t 0 ]; then
    echo ""
    echo "PyTorch is optional (only needed for Netryx indexing or GeoCLIP)."
    echo "Options: none | tur | proot"
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
        echo "  proot-distro install ubuntu && proot-distro login ubuntu"
        echo "  apt update && apt install -y python3 python3-pip python3-venv git nmap"
        echo "  bash install-debian.sh"
        echo ""
        echo "Continuing native Termux setup (without PyTorch)..."
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

echo "==> Installing core Python dependencies (pure Python — must succeed)..."
pip_try \
    "textual>=0.80" \
    "rich>=13.0" \
    "InquirerPy>=0.3" \
    "prompt_toolkit>=3.0" \
    "wcwidth" \
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

echo "==> Installing optional/native dependencies..."
pip_try \
    "Pillow" \
    "lupa" \
    "paketlib" \
    "huggingface-hub" \
    "safetensors"

INSTALL_GEOCLIP="${LAITOXX_INSTALL_PLANET:-${LAITOXX_INSTALL_GEOCLIP:-}}"
if [ -z "$INSTALL_GEOCLIP" ] && [ -t 0 ]; then
    read -r -p "Install optional GeoCLIP Photo Geolocation? Requires PyTorch. [y/N] " INSTALL_GEOCLIP
fi
case "$(printf '%s' "${INSTALL_GEOCLIP:-}" | tr '[:upper:]' '[:lower:]')" in
    y|yes)
        echo "Installing optional GeoCLIP dependencies..."
        while IFS= read -r _pkg || [ -n "$_pkg" ]; do
            case "$_pkg" in ""|\#*) continue ;; esac
            pip_try "$_pkg"
        done < requirements-photo2geo-geoclip.txt
        ;;
esac

# ── Final summary ──────────────────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo " Installation summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -z "$PIP_FAILED" ] && [ -z "$PKG_FAILED" ]; then
    echo " All packages installed successfully."
else
    if [ -n "$PKG_FAILED" ]; then
        echo ""
        echo " pkg packages not found (optional, skip if unused):"
        for _p in $PKG_FAILED; do echo "   pkg install $_p"; done
    fi
    if [ -n "$PIP_FAILED" ]; then
        echo ""
        echo " pip packages that failed to build — install manually if needed:"
        for _p in $PIP_FAILED; do echo "   pip install $_p"; done
        echo ""
        echo " Tips:"
        echo "   lupa    → needs Lua headers: pkg install lua54"
        echo "   Pillow  → already available as: pkg install python-pillow"
        echo "   aiohttp → needs clang:         pkg install clang"
    fi
fi

echo ""
echo " Run:"
echo "   source .venv/bin/activate"
echo "   python cli.py"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
