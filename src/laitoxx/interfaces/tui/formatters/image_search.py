"""Formatter for the image search tool.

The image search tool might return multiple sections including a list
of sources and extracted metadata (EXIF, ELA, etc.).  For now this
formatter renders dictionaries and lists generically.
"""

from __future__ import annotations

from typing import Any

from ..display import print_key_value, print_result_panel, print_table


def format_result(result: Any, captured: str, console, theme) -> None:
    if isinstance(result, dict):
        for section, data in result.items():
            title = section.replace("_", " ").title()
            if isinstance(data, dict):
                print_key_value(console, data, theme, title=title)
            elif isinstance(data, list) and data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                rows = [[item.get(h, "") for h in headers] for item in data]
                print_table(console, headers, rows, theme, title=title)
            else:
                print_result_panel(console, title, str(data), theme)
        return
    if isinstance(result, list):
        if result and isinstance(result[0], dict):
            headers = list(result[0].keys())
            rows = [[item.get(h, "") for h in headers] for item in result]
            print_table(console, headers, rows, theme, title="Image Search Results")
        else:
            print_result_panel(console, "Image Search Results", "\n".join(map(str, result)), theme)
        return
    content = captured or str(result)
    print_result_panel(console, "Image Search", content, theme)
