"""Terminal cleanup helpers for the Textual TUI."""

from __future__ import annotations

import sys
from contextlib import suppress

MOUSE_RESET_SEQUENCE = (
    "\x1b[?9l"
    "\x1b[?1000l"
    "\x1b[?1002l"
    "\x1b[?1003l"
    "\x1b[?1004l"
    "\x1b[?1005l"
    "\x1b[?1006l"
    "\x1b[?1015l"
    "\x1b[?1016l"
    "\x1b[?2004l"
    "\x1b[?25h"
)


def reset_terminal_modes() -> None:
    """Disable terminal modes that can leak after an interrupted TUI session."""
    with suppress(Exception):
        output = getattr(sys, "__stdout__", sys.stdout)
        output.write(MOUSE_RESET_SEQUENCE)
        output.flush()
