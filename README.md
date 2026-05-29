# Laitoxx Multi-Tool TUI

**Version:** TUI Beta 1.0, based on Laitoxx Multi-Tool 2.3.

Laitoxx Multi-Tool TUI is a console-first OSINT and cybersecurity toolkit built on Python 3.13 and Textual. This edition is intended for terminal environments: Windows Terminal, Linux shells, SSH sessions, WSL and Termux-like mobile consoles.

The project keeps the existing tool registry, Lua plugin support, proxy-aware networking and report generation from the 2.3 codebase, but the primary interface is now the Textual TUI launched from `cli.py`.

## Purpose and Disclaimer

Use this software only for education, research, defensive security work and systems you are allowed to test. The authors are not responsible for misuse, unauthorized scanning or damage caused by this tool.

## Highlights

- Textual TUI with keyboard navigation, command palette, settings dialog and theme support.
- OSINT tools for phone, IP, email, Telegram, usernames, websites and images.
- Web and network utilities: HTTP inspector, technology detection, CMS audit, JWT analyzer, subdomain finder, crawler and Nmap integration.
- Photo geolocation with two modes: Netryx Astra V2 local/community indexes and GeoCLIP/PlaNet-like worldwide prediction.
- Lua plugin system through `lupa` with sandboxed file access and proxy-aware host HTTP helpers.
- Proxy settings for HTTP, HTTPS and SOCKS5 from the TUI settings window.
- HTML report generation for collected results.
- Platform installers for Windows, Debian/Ubuntu/Kali and native Termux.

## Requirements

- Python 3.13 or newer.
- A terminal with ANSI color support.
- `nmap` executable in `PATH` for the Nmap tool.
- Optional root/admin privileges for Nmap profiles that require raw packet features. The TUI Nmap tool checks this at runtime and reports whether root/admin is available.
- Optional Netryx Astra source path for the Netryx Photo geolocation mode. Set `NETRYX_ASTRA_PATH` or fill the Source path field in the tool form.
- Optional GeoCLIP package for the global Photo geolocation mode. Original Google PlaNet weights are not public, so Laitoxx uses the open `geoclip` package for this workflow.

Install Nmap separately:

```bash
# Debian/Ubuntu/Kali
sudo apt install nmap

# Termux
pkg install nmap

# macOS
brew install nmap
```

On Windows, install Nmap from the official installer or a package manager such as winget/choco, then make sure `nmap.exe` is available in `PATH`.

## Installation

### Debian/Ubuntu/Kali

```bash
git clone https://github.com/Laitoxx/Laitoxx-Multi-Tool.git
cd Laitoxx-Multi-Tool
python3 install.py
source .venv/bin/activate
python cli.py
```

Direct platform installer:

```bash
bash install-debian.sh
source .venv/bin/activate
python cli.py
```

### Native Termux

```bash
pkg update
pkg install git
git clone https://github.com/Laitoxx/Laitoxx-Multi-Tool.git
cd Laitoxx-Multi-Tool
python install.py
source .venv/bin/activate
python cli.py
```

Direct platform installer:

```bash
bash install-termux.sh
source .venv/bin/activate
python cli.py
```

For PyTorch-dependent Photo geolocation features in native Termux, run the installer with `PHOTO2GEO_TORCH=tur` to use TUR packages, or choose `proot` and install inside Ubuntu/Debian through `proot-distro`.

### macOS and Other Unix Shells

```bash
git clone https://github.com/Laitoxx/Laitoxx-Multi-Tool.git
cd Laitoxx-Multi-Tool
python3 install.py
source .venv/bin/activate
python cli.py
```

Direct fallback installer:

```bash
bash install.sh
source .venv/bin/activate
python cli.py
```

### Windows

```bat
git clone https://github.com/Laitoxx/Laitoxx-Multi-Tool.git
cd Laitoxx-Multi-Tool
python install.py
.venv\Scripts\activate.bat
python cli.py
```

Direct platform installer:

```bat
install.bat
.venv\Scripts\activate.bat
python cli.py
```

`install.py` is the unified auto selector. It chooses Windows, native Termux, Debian/Ubuntu/Kali or generic Unix automatically. `install.sh` still dispatches to `install-debian.sh` on apt-based systems and to `install-termux.sh` in native Termux. `install.bat` dispatches to `install-windows.bat`.

Installer options:

```bash
# Install the optional PlaNet-like/GeoCLIP Photo Geolocation dependencies
python install.py --install-planet

# Skip the optional PlaNet-like/GeoCLIP dependencies without prompting
python install.py --skip-planet

# Native Termux PyTorch setup through TUR
python install.py --install-planet --termux-torch tur

# Show selected installer and options without running installation
python install.py --install-planet --dry-run

# Disable the animated installer status line
python install.py --no-animation
```

During installation `install.py` shows an animated status line with the latest installer output. If the installer exits with an error, it prints the captured log.

## Manual Setup

```bash
python -m venv .venv
source .venv/bin/activate        # Linux/macOS/Termux
# .venv\Scripts\activate.bat     # Windows
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python cli.py
```

## Running the TUI

Start the console interface:

```bash
python cli.py
```

Common keys:

- `/` or `f`: focus tool filter.
- `m`: focus tool menu.
- `Enter` or `r`: run selected tool.
- `o`: focus output.
- `s`: save HTML report.
- `,` or `Ctrl+,`: open settings.
- `Ctrl+P`: command palette.
- `q`: quit.

## Nmap Notes

The Nmap module uses the system `nmap` CLI and parses XML output from `nmap -oX -`. Before a scan it checks:

- whether `nmap` exists in `PATH`;
- current platform;
- whether the process has root/admin privileges;
- whether the selected profile requires elevated privileges.

Current default profiles are conservative and usually work without root/admin, but raw packet profiles added later will be blocked unless the process is elevated.

## Photo Geolocation

The `Photo geolocation` tool is available under the information gathering category. It has a `Geolocation mode` switcher:

- `Netryx Astra local index`: local/community index workflow using Netryx compact indexes.
- `GeoCLIP / PlaNet-like global`: worldwide image-to-GPS prediction through the open `geoclip` package. This is the Laitoxx PlaNet-like mode; Google's original PlaNet source/weights are not required.

Both modes use a Textual-native workflow. Heavy Photo geolocation jobs run in an isolated Python worker process; the parent Textual UI stays responsive, keeps handling keyboard/mouse input and shows animated loading/progress panels while the worker is active.

The TUI form changes with the selected operation, so it only shows the relevant inputs:

- `Check setup`: verifies Netryx path, dependencies and index files.
- `Find photo location` in Netryx mode: uses a photo path plus a location hint like `55.75, 37.62, 2`.
- `Find photo location` in GeoCLIP mode: uses only a photo path, result count, device and precision settings.
- `Create local index`: enter a latitude/longitude center and radius, then let the worker scan Street View coverage, download directional panorama crops, extract MegaLoc descriptors and save the compact local index. The progress panel reports the current stage, completed/remaining work and estimated time; the job can be cancelled until final PCA/index assembly begins.
- `Search community indexes`: type a city name, then use `Download` beside an index or `Download all` in the results panel. Bundle downloads show progress, speed and remaining time, and can be cancelled before installation.
- `Import .netryx index`: choose a local `.netryx` file with the built-in file picker.
- `Export current index`: type the output `.netryx` file path.

For local files and folders, use the `Browse` button in the form. It opens a terminal file explorer, so users do not need to type full paths manually. Text values still work in the same field for city names and Hugging Face repo ids.

By default it looks for Netryx Astra at the path configured in `NETRYX_ASTRA_PATH`; on the development machine the fallback path is `C:/Users/ShShu/Downloads/Netryx-Astra-V2-Geolocation-Tool-main/Netryx-Astra-V2-Geolocation-Tool-main`.

Heavy AI dependencies such as `torch`, `torchvision`, `opencv-python`, `scikit-learn`, `timm`, `safetensors`, `einops` and `huggingface-hub` are included in `requirements.txt`, but model weights and MASt3R setup are still managed by Netryx Astra itself. GeoCLIP is optional and can be installed with:

```bash
python -m pip install -r requirements-photo2geo-geoclip.txt
```

PlaNet-like/GeoCLIP model downloads are directed to the project folder:

```text
models/photo_geolocation/planet/
```

`Check setup` in the GeoCLIP/PlaNet-like mode reports whether this folder exists, how many cache/model files it contains, total cache size and whether a model-like weight file is present.

On Termux, use `bash install-termux.sh` instead of the Debian installer. Native PyTorch usually needs TUR (`PHOTO2GEO_TORCH=tur bash install-termux.sh`) or a proot Debian/Ubuntu environment; plain `pip install torch` is not reliable on Android.

Local index construction creates visual descriptors tied to Street View coordinates and headings rather than storing an EXIF/GPS lookup for the query image. `Grid resolution` controls coverage density and runtime; the default `300` is intentionally expensive for large areas.

## Lua Plugins

Lua plugins live in `lua_plugins/`. The local plugin API guide is available in [docs/guides/plugin-building.md](./docs/guides/plugin-building.md).

The TUI discovers enabled Lua plugins on startup. Plugin file access is sandboxed to the plugin directory, and HTTP helpers use the configured proxy session.

## Development Checks

```bash
python -m ruff check .
python -m ruff format .
python -m pytest
python scripts/check-structure.py
python -m compileall -q src tests laitoxx cli.py gui.py install.py
```

## Project Layout

```text
src/laitoxx/app/                 Composition layer, registries, Lua plugin runtime
src/laitoxx/core/                Settings, config, localization, installer orchestration
src/laitoxx/features/            OSINT, network, web audit, crypto and utility features
src/laitoxx/interfaces/          CLI, Textual TUI and legacy PyQt GUI adapters
src/laitoxx/shared/              Reusable helpers and graph models
laitoxx/                         Compatibility shim for `python -m laitoxx...`
config/                          Runtime app settings and environment templates
resources/data/                  Local data files, including username site database
resources/translations/          Translation JSON files
resources/themes/                Theme JSON files
resources/background/            GUI/TUI background assets
lua_plugins/                     Lua plugins and generated plugin artifacts
public/                          Documentation images and examples
docs/                            Architecture, guides and legal text
tests/                           Regression tests
requirements.txt                    Full desktop/server Python dependencies
requirements-termux.txt             Native Termux TUI dependencies
requirements-photo2geo-geoclip.txt  Optional GeoCLIP package
install.sh                          Unix dispatcher installer
install-debian.sh                   Debian/Ubuntu/Kali installer
install-termux.sh                   Native Termux installer
install-windows.bat                 Windows installer
install.bat                         Windows compatibility wrapper
install.py                          Cross-platform installer auto selector
models/photo_geolocation/planet/    PlaNet-like/GeoCLIP project model cache
```

Architecture rules are documented in [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md).

---

# Laitoxx Multi-Tool TUI (ru)

Это TUI-версия Laitoxx для консольных интерфейсов: Windows Terminal,
Linux/WSL, SSH, Termux и других терминалов. Основной запуск выполняется
через `python cli.py`.

## Быстрый запуск

Linux/macOS/WSL/Termux:

```bash
bash install.sh
source .venv/bin/activate
python cli.py
```

Windows:

```bat
install.bat
.venv\Scripts\activate.bat
python cli.py
```

Для Nmap-инструмента нужен установленный `nmap` в `PATH`. Перед
сканированием модуль проверяет окружение и наличие root/admin-прав. Профили,
которым нужны повышенные права, не запускаются без них.
