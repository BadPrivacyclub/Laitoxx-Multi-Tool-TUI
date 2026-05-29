"""Formatter for the Username OSINT tool.

The username OSINT tool can return a mixture of live output and a final
result summarising discovered profiles.  This formatter tries to
interpret the structure and show it in a table.  Unknown structures
fall back to captured text.
"""

from __future__ import annotations

from typing import Any

from ..display import print_result_panel, print_table


def format_result(result: Any, captured: str, console, theme) -> None:
    # When result is a list of dicts with 'site' and 'url' keys, render a table
    if isinstance(result, list) and result and isinstance(result[0], dict):
        headers = list(result[0].keys())
        rows = [[item.get(h, "") for h in headers] for item in result]
        print_table(console, headers, rows, theme, title="Found Accounts")
        return
    # Otherwise show captured output
    content = captured or str(result)
    print_result_panel(console, "Username OSINT", content, theme)
