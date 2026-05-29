"""Semantic styling helpers for the TUI."""

from __future__ import annotations

from rich import box


class TUIStyle:
    """Central style names used by Rich renderers."""

    BOX = box.ROUNDED
    PANEL_BOX = box.ROUNDED
    TABLE_BOX = box.SIMPLE_HEAVY

    PRIMARY = "cyan"
    ACCENT = "magenta"
    TEXT = "white"
    MUTED = "dim"
    SUCCESS = "bold green"
    WARNING = "bold yellow"
    ERROR = "bold red"
    TITLE = "bold cyan"

    OK = "OK"
    FAIL = "FAIL"
    INFO = "INFO"
