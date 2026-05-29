"""Formatter for the port scanner tool.

The port scanner returns a list of open ports or a dict mapping
port numbers to service names.  This formatter displays them in a
simple two–column table.
"""

from __future__ import annotations

from typing import Any

from ..display import print_result_panel, print_table


def format_result(result: Any, captured: str, console, theme) -> None:
    if isinstance(result, dict):
        rows = [[port, service] for port, service in result.items()]
        print_table(console, ["Port", "Service"], rows, theme, title="Open Ports")
        return
    if isinstance(result, list):
        # Assume list of ports
        rows = [[p] for p in result]
        print_table(console, ["Port"], rows, theme, title="Open Ports")
        return
    content = captured or str(result)
    print_result_panel(console, "Port Scanner", content, theme)
