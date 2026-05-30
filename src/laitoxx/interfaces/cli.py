"""Command-line entry point for the Laitoxx Textual interface."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from InquirerPy import inquirer
from rich.console import Console

from laitoxx.core.settings.app_settings import AppSettings
from laitoxx.core.settings.paths import USER_AGREEMENT_FILE
from laitoxx.core.settings.proxy import apply_proxy_settings
from laitoxx.core.settings.tos import is_accepted, mark_accepted

LOGGER = logging.getLogger(__name__)
TOS_FILE = USER_AGREEMENT_FILE

REPO_URL = "https://github.com/BadPrivacyclub/Laitoxx-Multi-Tool-TUI.git"
_PROJECT_ROOT = Path(__file__).resolve().parents[4]


def _check_for_updates(console: Console) -> bool:
    """Return True if remote has new commits. Silently skips if git/network unavailable."""
    try:
        result = subprocess.run(
            ["git", "fetch", "--dry-run", "origin", "main"],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=6,
        )
        behind = subprocess.run(
            ["git", "rev-list", "--count", "HEAD..origin/main"],
            cwd=_PROJECT_ROOT,
            capture_output=True,
            text=True,
            timeout=6,
        )
        count = int(behind.stdout.strip() or "0")
        if count > 0:
            console.print(
                f"\n[bold yellow]⬆  Update available:[/] {count} new commit(s) on main.\n"
                f"   Run [bold cyan]git pull[/] in the project folder to update, "
                f"then re-run [bold cyan]bash install-termux.sh[/] (or install-debian.sh) "
                f"to refresh dependencies.",
                highlight=False,
            )
            if sys.stdin.isatty():
                do_update = inquirer.confirm(
                    message="Pull and update now?", default=False
                ).execute()
                if do_update:
                    _do_update(console)
                    return True
        return False
    except Exception:  # noqa: BLE001
        return False


def _do_update(console: Console) -> None:
    """Run git pull and reinstall dependencies."""
    console.print("[cyan]Pulling latest changes…[/]")
    try:
        subprocess.run(["git", "pull", "--ff-only", "origin", "main"],
                       cwd=_PROJECT_ROOT, check=True, timeout=60)
    except subprocess.CalledProcessError as exc:
        console.print(f"[red]git pull failed:[/] {exc}")
        return

    # Detect platform and re-run the right installer
    req = _PROJECT_ROOT / "requirements.txt"
    req_termux = _PROJECT_ROOT / "requirements-termux.txt"
    venv_pip = _PROJECT_ROOT / ".venv" / "bin" / "python"
    if not venv_pip.exists():
        venv_pip = _PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"

    if venv_pip.exists():
        in_termux = bool(subprocess.run(
            ["command", "-v", "pkg"], shell=True, capture_output=True).returncode == 0)
        req_file = str(req_termux if in_termux else req)
        console.print(f"[cyan]Re-installing dependencies from {req_file}…[/]")
        subprocess.run(
            [str(venv_pip), "-m", "pip", "install", "--prefer-binary", "-r", req_file],
            check=False, timeout=300,
        )
    console.print("[green]Update complete.[/] Restart cli.py to apply changes.")
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
        return Path(TOS_FILE).read_text(encoding="utf-8").strip()
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

    _check_for_updates(console)

    settings = AppSettings()
    apply_proxy_settings(settings.proxy)

    app = _load_tui_app()(settings=settings, console=console)
    try:
        app.run()
    except KeyboardInterrupt:
        console.print("\nExiting...", style="italic")


if __name__ == "__main__":
    main(sys.argv[1:])
