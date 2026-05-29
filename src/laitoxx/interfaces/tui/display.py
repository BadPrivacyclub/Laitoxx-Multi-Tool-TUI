"""Helper functions for rendering output in the text interface.

This module centralises the use of common ``rich`` constructs such as
``Panel``, ``Table`` and ``Tree``.  By funnelling all output through
these helpers we ensure consistent styling across the entire
application and isolate low–level ``rich`` usage from the rest of the
codebase.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree


def print_result_panel(console: Console, title: str, content: str, theme: dict) -> None:
    """Display arbitrary text inside a bordered panel.

    The panel border and title use the accent colour defined by the
    current theme.  The content may include Markdown or Rich markup.

    Parameters
    ----------
    console: Console
        The console to write to.
    title: str
        Title displayed at the top of the panel.
    content: str
        Raw text to display inside the panel.
    theme: dict
        A theme mapping as returned by ``theme_adapter.load_theme``.
    """
    border_style = theme.get("accent", "cyan")
    console.print(
        Panel(
            content,
            title=title,
            title_align="left",
            border_style=border_style,
            expand=True,
        )
    )


def print_table(
    console: Console,
    headers: Iterable[str],
    rows: Iterable[Iterable[Any]],
    theme: dict,
    title: str | None = None,
) -> None:
    """Render a simple table with zebra striping.

    Parameters
    ----------
    console: Console
        The console to write to.
    headers: iterable of str
        Column headings.
    rows: iterable of iterables
        Each inner iterable represents a row.
    theme: dict
        Theme mapping for colours.
    title: str, optional
        Optional table title.
    """
    table = Table(title=title, expand=True, show_lines=False)
    for header in headers:
        table.add_column(str(header), style=theme.get("accent"))
    for idx, row in enumerate(rows):
        style = None
        # Apply zebra striping: alternate background for odd rows
        if idx % 2 == 1:
            style = theme.get("text_secondary")
        table.add_row(*[str(cell) for cell in row], style=style)
    console.print(table)


def print_key_value(
    console: Console, data: dict[str, Any], theme: dict, title: str | None = None
) -> None:
    """Display a mapping as a two–column table.

    Parameters
    ----------
    console: Console
        The console to write to.
    data: dict
        Mapping of key → value.
    theme: dict
        Theme mapping.
    title: str, optional
        Optional title for the table.
    """
    table = Table(title=title, expand=True, show_lines=False)
    table.add_column("Key", style=theme.get("accent"))
    table.add_column("Value", style=theme.get("text"))
    for key, value in data.items():
        table.add_row(str(key), str(value))
    console.print(table)


def print_tree(
    console: Console, data: dict[str, Any], theme: dict, title: str | None = None
) -> None:
    """Render nested dictionaries as a tree structure.

    Parameters
    ----------
    console: Console
        Console to render to.
    data: dict
        Nested mapping to display.
    theme: dict
        Theme mapping.
    title: str, optional
        Root label for the tree.
    """
    root_label = title or "Root"
    root = Tree(root_label, guide_style=str(theme.get("accent", "cyan")))
    _build_tree(root, data, theme)
    console.print(root)


def _build_tree(node: Tree, data: dict[str, Any], theme: dict) -> None:
    for key, value in data.items():
        if isinstance(value, dict):
            child = node.add(str(key))
            _build_tree(child, value, theme)
        else:
            node.add(f"[bold]{key}[/]: {value}")


def print_error(console: Console, msg: str, theme: dict) -> None:
    """Print an error message inside a red panel."""
    console.print(Panel(msg, border_style=theme.get("error", "red")))


def print_success(console: Console, msg: str, theme: dict) -> None:
    """Print a success message inside a green panel."""
    console.print(Panel(msg, border_style=theme.get("success", "green")))
