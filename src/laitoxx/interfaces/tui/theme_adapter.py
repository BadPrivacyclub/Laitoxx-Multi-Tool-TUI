"""Convert GUI JSON themes into Rich style definitions.

The GUI version of Laitoxx stores theme definitions as JSON files under
``resources/themes``.  Each file contains a number of RGBA or hex
colour definitions tailored for use with PyQt6 widgets.  This module
provides a simple adapter that reads the selected theme and exposes
styles that can be used with the ``rich`` library.

Only a handful of keys are mapped explicitly: ``accent_color`` for
borders and highlights, ``border_color`` for table/box borders and
``button_text_color`` for the primary text colour.  Additional keys
defined in the JSON will be available via the returned dictionary but
are not guaranteed to be ``rich.style.Style`` instances.
"""

from __future__ import annotations

import json
import os
from typing import Any

from rich.style import Style

from laitoxx.core.settings.paths import ROOT_DIR


def load_theme(theme_path: str) -> dict[str, Any]:
    """Load a theme JSON file and convert it into a dictionary of styles.

    Parameters
    ----------
    theme_path: str
        Absolute path to the theme JSON file.  Relative paths are resolved
        relative to the project root (``resources/themes``).

    Returns
    -------
    dict
        A dictionary containing style objects keyed by semantic names.
    """
    if not os.path.isabs(theme_path):
        theme_path = os.path.normpath(os.path.join(ROOT_DIR, theme_path))

    try:
        with open(theme_path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        data = {}

    # Helper to coerce a hex or rgba string into a valid Style
    def to_style(key: str, default: str = "white", bold: bool = False) -> Style:
        colour = data.get(key, default)
        # rich understands hex strings; remove rgba alpha channel if present
        if isinstance(colour, str) and colour.startswith("rgba("):
            # Extract the RGB part: rgba(r, g, b, a)
            try:
                parts = colour[5:-1].split(",")
                r, g, b = [int(float(p.strip())) for p in parts[:3]]
                colour = f"#{r:02x}{g:02x}{b:02x}"
            except Exception:
                colour = default
        return Style(color=colour, bold=bold)

    theme: dict[str, Any] = {
        # Primary accent colour used for borders, highlights and headings
        "accent": to_style("accent_color", default="cyan", bold=True),
        # Dimmed accent for secondary emphasis
        "accent_dim": to_style("accent_dim_color", default="cyan"),
        # Primary text colour
        "text": to_style("button_text_color", default="white"),
        # Secondary text colour
        "text_secondary": to_style("text_secondary_color", default="grey70"),
        # Border colour for panels and tables
        "border": to_style("border_color", default="grey50"),
        # Error and success colours are hardcoded for clarity
        "error": Style(color="red", bold=True),
        "success": Style(color="green", bold=True),
    }

    # Include the raw data so custom colours can be accessed by other
    # modules if needed (e.g. generating HTML reports).  Keys from the
    # JSON that aren't handled above will remain as strings.
    theme.update(data)
    return theme
