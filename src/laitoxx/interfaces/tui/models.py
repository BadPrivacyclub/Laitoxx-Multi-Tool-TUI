"""Shared data models for the Textual interface."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from laitoxx.app.plugins.engine import LuaPluginMeta
    from laitoxx.app.tool_registry import ToolSpec


@dataclass(frozen=True)
class ToolItem:
    """A Python tool or Lua plugin visible in the TUI."""

    name: str
    category: str
    kind: str
    spec: ToolSpec | None = None
    plugin: LuaPluginMeta | None = None


@dataclass(frozen=True)
class Field:
    """Input field declaration used to build native Textual forms."""

    name: str
    label: str
    kind: str = "text"
    default: Any = ""
    options: tuple[tuple[str, Any], ...] = ()
    enabled: tuple[Any, ...] = ()
