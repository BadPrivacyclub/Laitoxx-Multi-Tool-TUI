"""Formatter for the IP lookup tool.

This formatter interprets the return value of ``script.tools.ip_info.get_ip``
and displays it using tables and panels.  The tool typically returns a
dictionary with keys such as ``geolocation``, ``asn``, ``reputation`` and
``shodan``.  Unknown keys are rendered generically.
"""

from __future__ import annotations

from typing import Any

from ..display import print_key_value, print_result_panel, print_table


def format_result(result: Any, captured: str, console, theme) -> None:
    # If the result is not a dict, fall back to captured output
    if not isinstance(result, dict):
        content = captured or str(result)
        print_result_panel(console, "IP Info", content, theme)
        return
    # Render each top–level key as its own table or panel
    for section, data in result.items():
        title = section.replace("_", " ").title()
        if isinstance(data, dict):
            print_key_value(console, data, theme, title=title)
        elif isinstance(data, list):
            # Attempt to display as table if list of dicts
            if data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [[item.get(h, "") for h in headers] for item in data]
                print_table(console, headers, rows, theme, title=title)
            else:
                print_result_panel(console, title, "\n".join(map(str, data)), theme)
        else:
            print_result_panel(console, title, str(data), theme)
