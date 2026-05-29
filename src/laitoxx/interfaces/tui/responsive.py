"""Responsive layout decisions for the Textual interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TableLayoutMode = Literal["full", "compact", "phone"]


@dataclass(frozen=True)
class ResponsiveState:
    """Terminal-size dependent UI state."""

    width: int
    height: int
    compact: bool
    narrow: bool
    micro: bool
    short: bool
    phone: bool
    table_mode: TableLayoutMode


def detect_responsive_state(width: int, height: int) -> ResponsiveState:
    """Return responsive classes and table density for a terminal size."""
    compact = width < 112
    narrow = width < 88
    micro = width < 64
    short = height < 24
    phone = width < 72 or height < 22
    table_mode: TableLayoutMode = "phone" if phone else "compact" if narrow else "full"

    return ResponsiveState(
        width=width,
        height=height,
        compact=compact,
        narrow=narrow,
        micro=micro,
        short=short,
        phone=phone,
        table_mode=table_mode,
    )
