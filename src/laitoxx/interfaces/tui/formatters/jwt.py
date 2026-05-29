"""Formatter for the JWT analyzer tool.

The JWT analyzer returns a dictionary containing decoded header,
payload and claims.  This formatter uses ``rich.syntax.Syntax`` to
highlight JSON sections and tables to display claims.
"""

from __future__ import annotations

from typing import Any

from rich.syntax import Syntax

from ..display import print_key_value, print_result_panel


def format_result(result: Any, captured: str, console, theme) -> None:
    if not isinstance(result, dict):
        content = captured or str(result)
        print_result_panel(console, "JWT Analyzer", content, theme)
        return
    # Display header and payload as highlighted JSON
    for section in ("header", "payload"):
        content = result.get(section)
        if content is not None:
            try:
                json_text = content if isinstance(content, str) else str(content)
                syntax = Syntax(json_text, "json", theme="monokai", line_numbers=False)
                console.print(syntax)
            except Exception:
                print_result_panel(console, section.title(), str(content), theme)
    # Display claims table if present
    claims = result.get("claims")
    if isinstance(claims, dict):
        print_key_value(console, claims, theme, title="Claims")
