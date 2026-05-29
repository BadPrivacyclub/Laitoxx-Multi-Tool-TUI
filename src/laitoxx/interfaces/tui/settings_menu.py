"""Interactive settings editor for the CLI.

This module exposes a function that allows users to adjust
application settings such as the active theme, proxy configuration
and language using simple terminal prompts.  Only a subset of the
settings available in the GUI are exposed here for brevity.
"""

from __future__ import annotations

import os
from glob import glob

from InquirerPy import inquirer

from laitoxx.core.settings.app_settings import AppSettings
from laitoxx.core.settings.paths import ROOT_DIR, THEMES_DIR


def open_settings_menu(settings: AppSettings, console) -> None:
    """Enter a loop for editing settings until the user chooses to go back."""
    while True:
        choice = inquirer.select(
            message="Settings",
            choices=[
                {"name": "Theme", "value": "theme"},
                {"name": "Proxy", "value": "proxy"},
                {"name": "Language", "value": "language"},
                {"name": "Back", "value": "back"},
            ],
        ).execute()
        if choice == "back":
            break
        if choice == "theme":
            _edit_theme(settings)
        elif choice == "proxy":
            _edit_proxy(settings)
        elif choice == "language":
            _edit_language(settings)


def _edit_theme(settings: AppSettings) -> None:
    """Allow the user to choose a theme from the resources/themes folder."""
    files = sorted(glob(os.path.join(THEMES_DIR, "*.json")))
    choices = [{"name": os.path.basename(f), "value": f} for f in files]
    selected = inquirer.select(message="Select theme", choices=choices, default=0).execute()
    if selected:
        # Store the path relative to the project root.  AppSettings will
        # normalise it to a portable representation.
        rel = os.path.relpath(selected, ROOT_DIR)
        settings.theme_path = rel


def _edit_proxy(settings: AppSettings) -> None:
    """Prompt the user to configure proxy settings."""
    cfg = settings.proxy or {}
    enabled = inquirer.confirm(message="Enable proxy?", default=cfg.get("enabled", False)).execute()
    cfg["enabled"] = enabled
    if enabled:
        proxy_type = inquirer.select(
            message="Proxy type",
            choices=["http", "https", "socks5"],
            default=cfg.get("type", "http"),
        ).execute()
        host = inquirer.text(message="Proxy host:", default=cfg.get("host", "")).execute()
        port = inquirer.text(message="Proxy port:", default=str(cfg.get("port", ""))).execute()
        username = inquirer.text(
            message="Proxy username (optional):", default=cfg.get("username", "")
        ).execute()
        password = inquirer.secret(
            message="Proxy password (optional):", default=cfg.get("password", "")
        ).execute()
        cfg.update(
            {
                "type": proxy_type,
                "host": host.strip(),
                "port": port.strip(),
                "username": username.strip(),
                "password": password.strip(),
            }
        )
    settings.proxy = cfg


def _edit_language(settings: AppSettings) -> None:
    """Switch between supported languages (currently EN and RU)."""
    lang = inquirer.select(
        message="Language",
        choices=[
            {"name": "English", "value": "en"},
            {"name": "Russian", "value": "ru"},
        ],
        default=settings.language,
    ).execute()
    if lang:
        settings.language = lang
