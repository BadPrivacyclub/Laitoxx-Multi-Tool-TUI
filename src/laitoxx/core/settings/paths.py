"""Central path definitions for settings and resource files."""

from __future__ import annotations

from pathlib import Path


def _find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parents[4]


ROOT_DIR = _find_project_root()


def _path(*parts: str) -> str:
    """Return an absolute project path as ``str`` for legacy callers."""
    return str(ROOT_DIR.joinpath(*parts))


CONFIG_DIR = _path("config")
SETTINGS_DIR = CONFIG_DIR
APP_SETTINGS_FILE = _path("config", "app_settings.json")

RESOURCES_DIR = _path("resources")
DATA_DIR = _path("resources", "data")
ICONS_DIR = _path("resources", "icons")
THEMES_DIR = _path("resources", "themes")
BACKGROUND_DIR = _path("resources", "background")
TRANSLATIONS_DIR = _path("resources", "translations")

LEGACY_BG_CONFIG = _path("background_config.txt")
LEGACY_THEME_CONFIG = _path("last_theme.txt")
LEGACY_AGREEMENT = _path("config", "user_agreement_accepted.txt")
LEGACY_LUA_SETTINGS = _path("config", "lua_plugin_settings.json")
TOS_FILE = _path("config", "tos_accepted.txt")
USER_AGREEMENT_FILE = _path("docs", "legal", "user-agreement.txt")

DEFAULT_THEME_FILE = _path("resources", "themes", "default.json")
DEFAULT_BG_FILE = _path("resources", "background", "background0.gif")


def ensure_resource_dirs() -> None:
    """Create resource directories required by themes and backgrounds."""
    for directory in (CONFIG_DIR, DATA_DIR, THEMES_DIR, BACKGROUND_DIR, ICONS_DIR, TRANSLATIONS_DIR):
        Path(directory).mkdir(parents=True, exist_ok=True)
