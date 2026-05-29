from __future__ import annotations

from pathlib import Path

_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "laitoxx"
__path__ = [str(_SRC_PACKAGE)]
__version__ = "2.3"
