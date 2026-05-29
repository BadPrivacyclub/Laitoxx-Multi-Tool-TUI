"""Text user interface (TUI) for the Laitoxx OSINT toolkit.

This package provides a Rich/InquirerPy based alternative to the original
PyQt6 GUI. It exposes the :class:`~tui.app.TUIApp` entry point and
submodules for menus, runner, display helpers, settings editing and
report generation.  The TUI is designed to work in headless
environments such as Termux on Android devices while preserving the
underlying business logic of the existing tools (all code under
``script/`` remains untouched).
"""

from .app import TUIApp

__all__ = ["TUIApp"]
