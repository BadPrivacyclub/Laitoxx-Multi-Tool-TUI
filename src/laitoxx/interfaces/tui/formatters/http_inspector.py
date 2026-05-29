"""Formatter for the HTTP inspector tool.

The HTTP inspector returns a dictionary containing various sections
such as headers, TLS information, cookies and redirects.  Each
section is rendered separately.
"""

from __future__ import annotations

from typing import Any

from ..display import print_key_value, print_result_panel


def format_result(result: Any, captured: str, console, theme) -> None:
    if not isinstance(result, dict):
        content = captured or str(result)
        print_result_panel(console, "HTTP Inspector", content, theme)
        return
    for section, data in result.items():
        title = section.replace("_", " ").title()
        if isinstance(data, dict):
            print_key_value(console, data, theme, title=title)
        elif isinstance(data, list):
            # Flatten list of dicts to key-value pairs
            for idx, item in enumerate(data, start=1):
                print_key_value(
                    console,
                    item if isinstance(item, dict) else {f"Item {idx}": item},
                    theme,
                    title=f"{title} #{idx}",
                )
        else:
            print_result_panel(console, title, str(data), theme)
