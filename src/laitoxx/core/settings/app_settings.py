"""Persistent application settings stored in a single JSON file.

Theme and background paths are saved relative to the project root whenever
possible, which keeps the archive portable between machines.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .paths import (
    APP_SETTINGS_FILE,
    DEFAULT_BG_FILE,
    DEFAULT_THEME_FILE,
    LEGACY_BG_CONFIG,
    LEGACY_THEME_CONFIG,
    ROOT_DIR,
)

SettingsData = dict[str, Any]

_DEFAULTS: SettingsData = {
    "open_website_on_startup": True,
    "performance_mode": False,
    "language": "en",
    "theme_path": "",
    "tui_theme": "laitoxx-soft-neon",
    "background_path": "",
    "proxy": {
        "enabled": False,
        "type": "http",
        "host": "",
        "port": "",
        "username": "",
        "password": "",
    },
}
_DEFAULTS["theme_path"] = str(Path(DEFAULT_THEME_FILE).relative_to(ROOT_DIR))
_DEFAULTS["background_path"] = str(Path(DEFAULT_BG_FILE).relative_to(ROOT_DIR))


def _to_relative(path: str) -> str:
    """Return *path* relative to the project root when it is safe to do so."""
    candidate = Path(path)
    if not candidate.is_absolute():
        return candidate.as_posix()

    try:
        return candidate.resolve().relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return path


def _to_absolute(path: str) -> str:
    """Resolve *path* against the project root."""
    candidate = Path(path)
    if candidate.is_absolute():
        return str(candidate)
    return str(ROOT_DIR.joinpath(candidate))


def _is_inside_project(path: str) -> bool:
    """Return whether *path* resolves inside the project root."""
    try:
        Path(_to_absolute(path)).resolve().relative_to(ROOT_DIR)
    except ValueError:
        return False
    return True


class AppSettings:
    """Load, validate and persist application settings."""

    def __init__(self) -> None:
        self._data: SettingsData = {}
        self.load()

    def load(self) -> None:
        """Load settings from disk, migrating legacy files when needed."""
        settings_file = Path(APP_SETTINGS_FILE)
        if settings_file.exists():
            on_disk = self._read_json(settings_file)
        else:
            on_disk = self._migrate_from_legacy()

        self._data = _deep_merge(_DEFAULTS, on_disk)
        self._normalize_resource_paths()
        self.save()

    def save(self) -> None:
        """Persist settings with portable resource paths."""
        settings_file = Path(APP_SETTINGS_FILE)
        settings_file.parent.mkdir(parents=True, exist_ok=True)

        data_to_write = deepcopy(self._data)
        for key in ("theme_path", "background_path"):
            if data_to_write.get(key):
                data_to_write[key] = _to_relative(str(data_to_write[key]))

        settings_file.write_text(
            json.dumps(data_to_write, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )

    @property
    def open_website_on_startup(self) -> bool:
        return bool(self._data.get("open_website_on_startup", True))

    @open_website_on_startup.setter
    def open_website_on_startup(self, value: bool) -> None:
        self._data["open_website_on_startup"] = bool(value)
        self.save()

    @property
    def performance_mode(self) -> bool:
        return bool(self._data.get("performance_mode", False))

    @performance_mode.setter
    def performance_mode(self, value: bool) -> None:
        self._data["performance_mode"] = bool(value)
        self.save()

    @property
    def language(self) -> str:
        return str(self._data.get("language", "en"))

    @language.setter
    def language(self, value: str) -> None:
        self._data["language"] = value
        self.save()

    @property
    def theme_path(self) -> str:
        """Absolute path to the active theme file."""
        raw = str(self._data.get("theme_path", ""))
        return _to_absolute(raw) if raw else DEFAULT_THEME_FILE

    @theme_path.setter
    def theme_path(self, value: str) -> None:
        self._data["theme_path"] = _to_relative(value)
        self.save()

    @property
    def tui_theme(self) -> str:
        return str(self._data.get("tui_theme", "laitoxx-soft-neon"))

    @tui_theme.setter
    def tui_theme(self, value: str) -> None:
        self._data["tui_theme"] = value
        self.save()

    @property
    def background_path(self) -> str:
        """Absolute path to the active background file."""
        raw = str(self._data.get("background_path", ""))
        return _to_absolute(raw) if raw else ""

    @background_path.setter
    def background_path(self, value: str) -> None:
        self._data["background_path"] = _to_relative(value) if value else ""
        self.save()

    @property
    def proxy(self) -> SettingsData:
        return dict(self._data.get("proxy", {}))

    @proxy.setter
    def proxy(self, value: SettingsData) -> None:
        self._data["proxy"] = dict(value)
        self.save()

    def _normalize_resource_paths(self) -> None:
        for key, default in (
            ("theme_path", DEFAULT_THEME_FILE),
            ("background_path", DEFAULT_BG_FILE),
        ):
            raw = str(self._data.get(key, ""))
            if raw and not _is_inside_project(raw):
                self._data[key] = _to_relative(default)

        for key in ("theme_path", "background_path"):
            if self._data.get(key):
                self._data[key] = _to_relative(str(self._data[key]))

    def _migrate_from_legacy(self) -> SettingsData:
        """Build initial settings from old scattered config files."""
        migrated: SettingsData = {}
        for key, legacy_file in (
            ("theme_path", LEGACY_THEME_CONFIG),
            ("background_path", LEGACY_BG_CONFIG),
        ):
            path = _read_text_if_exists(Path(legacy_file))
            if path:
                migrated[key] = path
        return migrated

    @staticmethod
    def _read_json(path: Path) -> SettingsData:
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return loaded if isinstance(loaded, dict) else {}


def _read_text_if_exists(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _deep_merge(base: SettingsData, override: SettingsData) -> SettingsData:
    """Recursively merge *override* into a copy of *base*."""
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


settings = AppSettings()
