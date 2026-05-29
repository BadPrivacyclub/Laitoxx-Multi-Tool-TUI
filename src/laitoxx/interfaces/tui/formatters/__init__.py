"""Collection of specialised formatters for individual tools.

Each module in this package defines a ``format_result`` function with
the signature ``(result, captured, console, theme) -> None``.  The
function is responsible for rendering the raw return value and any
captured stdout/stderr using the helpers defined in ``tui.display``.
"""

__all__ = [
    "ip",
    "username_osint",
    "port_scanner",
    "http_inspector",
    "jwt",
    "image_search",
]
