"""Register Textual themes from Laitoxx JSON theme files."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from glob import glob

from textual.theme import Theme

from laitoxx.core.settings.paths import THEMES_DIR


def register_laitoxx_themes(app) -> list[str]:
    """Register bundled GUI themes as Textual themes and return their names."""
    registered: list[str] = []
    for name, theme in _built_in_mood_themes():
        app.register_theme(theme)
        registered.append(name)

    for path in sorted(glob(os.path.join(THEMES_DIR, "*.json"))):
        try:
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        name = "laitoxx-" + _slug(os.path.splitext(os.path.basename(path))[0])
        app.register_theme(_theme_from_json(name, data))
        registered.append(name)
    return registered


def _theme_from_json(name: str, data: dict) -> Theme:
    primary = _color(data.get("accent_color"), "#7dd3fc")
    secondary = _color(data.get("accent_dim_color"), "#38bdf8")
    foreground = _color(
        data.get("text_area_text_color") or data.get("button_text_color"), "#e8eaf0"
    )
    background = _color(data.get("window_bg_color"), "#0a0a0a")
    surface = _color(data.get("sidebar_bg_color"), "#111827")
    panel = _color(data.get("panel_bg_color"), "#171b24")
    border = _color(data.get("border_color"), primary)
    muted = _color(data.get("text_secondary_color"), "#9ca3af")
    return Theme(
        name=name,
        primary=primary,
        secondary=secondary,
        warning="#fbbf24",
        error="#ef4444",
        success="#22c55e",
        accent=secondary,
        foreground=foreground,
        background=background,
        surface=surface,
        panel=panel,
        dark=_is_dark(background),
        variables={
            "border": border,
            "border-blurred": _mix(border, background),
            "foreground-muted": muted,
            "input-selection-background": f"{primary} 30%",
            "footer-background": panel,
            "footer-key-foreground": primary,
            "block-cursor-background": primary,
            "block-cursor-foreground": background,
        },
    )


def _built_in_mood_themes() -> Iterable[tuple[str, Theme]]:
    yield (
        "laitoxx-terminal-amber",
        Theme(
            name="laitoxx-terminal-amber",
            primary="#f2c166",
            secondary="#8fd0a4",
            warning="#f59e0b",
            error="#ef4444",
            success="#8fd0a4",
            accent="#d98b3a",
            foreground="#f3ead7",
            background="#080807",
            surface="#11100d",
            panel="#18140f",
            dark=True,
            variables={
                "border": "#7a5a2a",
                "border-blurred": "#2a2419",
                "foreground-muted": "#a99b82",
                "input-selection-background": "#f2c166 25%",
                "footer-background": "#18140f",
                "footer-key-foreground": "#f2c166",
            },
        ),
    )
    yield (
        "laitoxx-soft-neon",
        Theme(
            name="laitoxx-soft-neon",
            primary="#8be9fd",
            secondary="#bd93f9",
            warning="#f1fa8c",
            error="#ff6b8a",
            success="#50fa7b",
            accent="#ff79c6",
            foreground="#edf2ff",
            background="#090a12",
            surface="#101322",
            panel="#161a2d",
            dark=True,
            variables={
                "border": "#39425f",
                "border-blurred": "#22283a",
                "foreground-muted": "#9aa7c7",
                "input-selection-background": "#8be9fd 25%",
                "footer-background": "#161a2d",
                "footer-key-foreground": "#8be9fd",
            },
        ),
    )


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "theme"


def _color(value, default: str) -> str:
    if not isinstance(value, str) or not value.strip():
        return default
    value = value.strip()
    if value.startswith("rgba(") or value.startswith("rgb("):
        nums = value[value.find("(") + 1 : value.rfind(")")].split(",")
        try:
            r, g, b = [max(0, min(255, int(float(part.strip())))) for part in nums[:3]]
        except (TypeError, ValueError):
            return default
        return f"#{r:02x}{g:02x}{b:02x}"
    return value


def _is_dark(hex_color: str) -> bool:
    color = hex_color.lstrip("#")
    if len(color) != 6:
        return True
    try:
        r, g, b = (int(color[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return True
    return (0.299 * r + 0.587 * g + 0.114 * b) < 128


def _mix(fg: str, bg: str) -> str:
    try:
        f = fg.lstrip("#")
        b = bg.lstrip("#")
        fr, fg_, fb = (int(f[i : i + 2], 16) for i in (0, 2, 4))
        br, bg_, bb = (int(b[i : i + 2], 16) for i in (0, 2, 4))
    except Exception:
        return "#334155"
    r = int(fr * 0.35 + br * 0.65)
    g = int(fg_ * 0.35 + bg_ * 0.65)
    blue = int(fb * 0.35 + bb * 0.65)
    return f"#{r:02x}{g:02x}{blue:02x}"
