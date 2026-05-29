"""Command-line entry point for the Laitoxx Textual interface."""

from __future__ import annotations

import logging
import sys

from InquirerPy import inquirer
from rich.console import Console

from laitoxx.core.settings.app_settings import AppSettings
from laitoxx.core.settings.paths import USER_AGREEMENT_FILE
from laitoxx.core.settings.proxy import apply_proxy_settings
from laitoxx.core.settings.tos import is_accepted, mark_accepted

LOGGER = logging.getLogger(__name__)
TOS_FILE = USER_AGREEMENT_FILE
TOS_FALLBACK_TEXT = (
    "By using this software you agree to use it solely for educational and "
    "research purposes. The authors take no responsibility for misuse or "
    "damage caused by this tool."
)


def configure_logging() -> None:
    """Configure process logging once for CLI runs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s:%(name)s:%(message)s",
    )


def _load_tos_text() -> str:
    try:
        return TOS_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        LOGGER.warning("Terms-of-Service file is missing; using fallback text.")
        return TOS_FALLBACK_TEXT


def _require_tos_acceptance(console: Console) -> bool:
    """Prompt the user to accept the ToS if it has not been accepted."""
    if is_accepted():
        return True

    console.print("\n[bold underline]Terms of Service[/]:\n")
    console.print(f"{_load_tos_text()}\n")
    accepted = inquirer.confirm(message="Do you accept these terms?", default=False).execute()
    if accepted:
        mark_accepted()
        return True

    console.print("You must accept the Terms of Service to run the CLI.", style="red")
    return False


def _load_tui_app():
    try:
        from laitoxx.interfaces.tui.app import TUIApp
    except ImportError as exc:
        raise RuntimeError(
            "Failed to import TUI modules. Ensure that 'rich', 'textual' and "
            "'InquirerPy' are installed (see requirements.txt)."
        ) from exc
    return TUIApp


def main(argv: list[str] | None = None) -> None:
    """Run the interactive TUI application."""
    del argv
    configure_logging()

    console = Console()
    if not _require_tos_acceptance(console):
        return

    settings = AppSettings()
    apply_proxy_settings(settings.proxy)

    app = _load_tui_app()(settings=settings, console=console)
    try:
        app.run()
    except KeyboardInterrupt:
        console.print("\nExiting...", style="italic")


if __name__ == "__main__":
    main(sys.argv[1:])
