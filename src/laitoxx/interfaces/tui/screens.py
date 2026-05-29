"""Modal screens used by the Textual interface."""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable
from dataclasses import replace
from glob import glob
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DirectoryTree,
    Input,
    Label,
    Select,
    SelectionList,
    Static,
    TextArea,
)

from laitoxx.core.settings.paths import ROOT_DIR, THEMES_DIR

from .localization import TuiTranslator
from .models import Field


class FilePickerScreen(ModalScreen[str | None]):
    """Small terminal file picker for fields that expect local paths."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(
        self,
        *,
        title: str,
        start_path: str | os.PathLike[str] | None = None,
        select_directories: bool = False,
        language: str | None = "en",
    ):
        super().__init__()
        self.title = title
        self.select_directories = select_directories
        self.start_path = self._resolve_start_path(start_path)
        self.i18n = TuiTranslator(language)

    def compose(self) -> ComposeResult:
        with Container(id="file-picker-dialog"):
            yield Label(self.title, id="input-title")
            yield Static(str(self.start_path), id="file-picker-path")
            yield DirectoryTree(self.start_path, id="file-picker-tree")
            with Horizontal(id="input-actions"):
                if self.select_directories:
                    yield Button(self.i18n.t("use_folder"), id="select-current", variant="success")
                yield Button(self.i18n.t("cancel"), id="cancel")

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        if not self.select_directories:
            self.dismiss(str(Path(event.path)))

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        path = Path(event.path)
        self.query_one("#file-picker-path", Static).update(str(path))
        if self.select_directories:
            self.start_path = path

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "select-current":
            self.dismiss(str(self.start_path))
            return
        self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)

    @staticmethod
    def _resolve_start_path(start_path: str | os.PathLike[str] | None) -> Path:
        if not start_path:
            return Path.cwd()

        path = Path(start_path).expanduser()
        if path.is_file():
            return path.parent
        if path.exists():
            return path
        return Path.cwd()


class ToolInputScreen(ModalScreen[dict[str, Any] | None]):
    """Generated input form for a tool or Lua plugin."""

    BINDINGS = [("escape", "cancel", "Cancel"), ("ctrl+s", "submit", "Run")]

    def __init__(
        self,
        title: str,
        fields: list[Field],
        field_resolver: Callable[[dict[str, Any]], list[Field]] | None = None,
        language: str | None = "en",
        submit_label: str | None = None,
    ):
        super().__init__()
        self.title = title
        self.fields = fields
        self.field_resolver = field_resolver
        self.i18n = TuiTranslator(language)
        self.submit_label = submit_label or self.i18n.t("run")
        self._values = {field.name: field.default for field in fields}
        self._dynamic_values = {
            field.name: field.default for field in fields if field.kind == "select"
        }

    def compose(self) -> ComposeResult:
        with Container(id="input-dialog"):
            yield Label(self.title, id="input-title")
            with Vertical(id="input-fields"):
                for field in self.fields:
                    yield from self._compose_field(field)
            with Horizontal(id="input-actions"):
                yield Button(self.submit_label, id="submit", variant="success")
                yield Button(self.i18n.t("cancel"), id="cancel")

    def _compose_field(self, field: Field) -> ComposeResult:
        if field.kind == "select":
            yield Label(field.label, classes="field-label")
            yield Select(
                field.options,
                value=field.default if field.default != "" else Select.NULL,
                allow_blank=False,
                id=f"field-{field.name}",
            )
            return
        if field.kind == "multi":
            yield Label(field.label, classes="field-label")
            selections = [(label, value, value in field.enabled) for label, value in field.options]
            yield SelectionList(*selections, id=f"field-{field.name}", compact=True)
            return
        if field.kind == "bool":
            yield Checkbox(
                field.label,
                value=bool(field.default),
                id=f"field-{field.name}",
                classes="boolean-field",
            )
            return
        if field.kind == "textarea":
            yield Label(field.label, classes="field-label")
            yield TextArea(str(field.default or ""), id=f"field-{field.name}")
            return
        if field.kind in {"file", "directory"}:
            yield Label(field.label, classes="field-label")
            with Horizontal(classes="path-field-row"):
                yield Input(value=str(field.default or ""), id=f"field-{field.name}")
                yield Button(
                    self.i18n.t("browse"),
                    id=f"browse-{field.name}",
                    classes="browse-button",
                )
            return

        yield Label(field.label, classes="field-label")
        yield Input(value=str(field.default or ""), id=f"field-{field.name}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id.startswith("browse-"):
            event.stop()
            self._open_path_picker(button_id.removeprefix("browse-"))
            return
        if event.button.id == "submit":
            self.action_submit()
        else:
            self.action_cancel()

    def on_select_changed(self, event: Select.Changed) -> None:
        if self.field_resolver is None or not str(event.select.id or "").startswith("field-"):
            return

        field_name = str(event.select.id).removeprefix("field-")
        if field_name in self._dynamic_values and event.value == self._dynamic_values[field_name]:
            return
        self._values.update({field.name: self._read_field_value(field) for field in self.fields})
        self._values[field_name] = event.value
        new_fields = self.field_resolver(self._values)
        self.fields = [
            replace(field, default=self._values[field.name])
            if field.name in self._values
            else field
            for field in new_fields
        ]
        self._dynamic_values = {
            field.name: field.default for field in self.fields if field.kind == "select"
        }
        self.refresh(recompose=True)

    def _open_path_picker(self, field_name: str) -> None:
        field = next((item for item in self.fields if item.name == field_name), None)
        if field is None:
            return

        widget = self.query_one(f"#field-{field_name}", Input)
        select_directories = field.kind == "directory"
        title = self.i18n.t("select_folder" if select_directories else "select_file")
        self.app.push_screen(
            FilePickerScreen(
                title=title,
                start_path=widget.value,
                select_directories=select_directories,
                language=self.i18n.language,
            ),
            callback=lambda selected: self._set_path_field(field_name, selected),
        )

    def _set_path_field(self, field_name: str, selected: str | None) -> None:
        if selected:
            self.query_one(f"#field-{field_name}", Input).value = selected

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss({field.name: self._read_field_value(field) for field in self.fields})

    def _read_field_value(self, field: Field) -> Any:
        widget = self.query_one(f"#field-{field.name}")
        if field.kind == "multi":
            return list(widget.selected)
        if field.kind == "bool":
            return bool(widget.value)
        if field.kind == "textarea":
            return widget.text
        return widget.value


class OpenReportScreen(ModalScreen[bool]):
    """Ask whether a generated report should be opened in the browser."""

    BINDINGS = [("escape", "cancel", "Cancel")]

    def __init__(self, title: str, path: str, language: str | None = "en") -> None:
        super().__init__()
        self.title = title
        self.path = path
        self.i18n = TuiTranslator(language)

    def compose(self) -> ComposeResult:
        with Container(id="input-dialog"):
            yield Label(self.title, id="input-title")
            yield Static(self.path, classes="field-label")
            with Horizontal(id="input-actions"):
                yield Button(self.i18n.t("open_report"), id="open", variant="success")
                yield Button(self.i18n.t("close"), id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "open")

    def action_cancel(self) -> None:
        self.dismiss(False)


class SettingsScreen(ModalScreen[dict[str, Any] | None]):
    """Native settings dialog for common TUI settings."""

    BINDINGS = [("escape", "cancel", "Cancel"), ("ctrl+s", "submit", "Save")]

    def __init__(
        self,
        settings,
        textual_themes: Iterable[str] = (),
        current_textual_theme: str = "textual-dark",
    ):
        super().__init__()
        self.settings = settings
        self.textual_themes = tuple(sorted(textual_themes)) or ("textual-dark", "textual-light")
        self.current_textual_theme = current_textual_theme
        self.i18n = TuiTranslator(getattr(settings, "language", "en"))

    def compose(self) -> ComposeResult:
        with Container(id="settings-dialog"):
            yield Label(self.i18n.t("settings"), id="input-title")
            with Vertical(id="input-fields"):
                yield Label(self.i18n.t("tui_theme"), classes="field-label")
                yield Select(
                    tuple((name, name) for name in self.textual_themes),
                    value=self._current_textual_theme_value(),
                    allow_blank=False,
                    id="settings-tui-theme",
                )
                yield Label(self.i18n.t("theme"), classes="field-label")
                theme_options = self._theme_options()
                yield Select(
                    theme_options,
                    value=self._current_theme_value(theme_options),
                    allow_blank=False,
                    id="settings-theme",
                )
                yield Label(self.i18n.t("language"), classes="field-label")
                yield Select(
                    ((self.i18n.t("language_en"), "en"), (self.i18n.t("language_ru"), "ru")),
                    value=getattr(self.settings, "language", "en") or "en",
                    allow_blank=False,
                    id="settings-language",
                )
                proxy = getattr(self.settings, "proxy", {}) or {}
                yield Label(self.i18n.t("proxy"), classes="field-label")
                yield Checkbox(
                    self.i18n.t("enable_proxy"),
                    value=bool(proxy.get("enabled", False)),
                    id="settings-proxy-enabled",
                )
                yield Label(self.i18n.t("proxy_type"), classes="field-label")
                yield Select(
                    (("HTTP", "http"), ("HTTPS", "https"), ("SOCKS5", "socks5")),
                    value=self._current_proxy_type(proxy),
                    allow_blank=False,
                    id="settings-proxy-type",
                )
                yield Label(self.i18n.t("proxy_host"), classes="field-label")
                yield Input(
                    value=str(proxy.get("host", "") or ""),
                    placeholder="127.0.0.1",
                    id="settings-proxy-host",
                )
                yield Label(self.i18n.t("proxy_port"), classes="field-label")
                yield Input(
                    value=str(proxy.get("port", "") or ""),
                    placeholder="1080",
                    restrict=r"[0-9]*",
                    id="settings-proxy-port",
                )
                yield Label(self.i18n.t("proxy_username"), classes="field-label")
                yield Input(
                    value=str(proxy.get("username", "") or ""),
                    placeholder=self.i18n.t("optional"),
                    id="settings-proxy-username",
                )
                yield Label(self.i18n.t("proxy_password"), classes="field-label")
                yield Input(
                    value=str(proxy.get("password", "") or ""),
                    placeholder=self.i18n.t("optional"),
                    password=True,
                    id="settings-proxy-password",
                )
            with Horizontal(id="input-actions"):
                yield Button(self.i18n.t("save"), id="submit", variant="success")
                yield Button(self.i18n.t("cancel"), id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit":
            self.action_submit()
        else:
            self.action_cancel()

    def action_cancel(self) -> None:
        self.dismiss(None)

    def action_submit(self) -> None:
        self.dismiss(
            {
                "language": self.query_one("#settings-language", Select).value,
                "tui_theme": self.query_one("#settings-tui-theme", Select).value,
                "theme_path": self.query_one("#settings-theme", Select).value,
                "proxy": self._read_proxy_settings(),
            }
        )

    def _read_proxy_settings(self) -> dict[str, Any]:
        return {
            "enabled": bool(self.query_one("#settings-proxy-enabled", Checkbox).value),
            "type": str(self.query_one("#settings-proxy-type", Select).value or "http"),
            "host": str(self.query_one("#settings-proxy-host", Input).value or "").strip(),
            "port": str(self.query_one("#settings-proxy-port", Input).value or "").strip(),
            "username": str(self.query_one("#settings-proxy-username", Input).value or "").strip(),
            "password": str(self.query_one("#settings-proxy-password", Input).value or ""),
        }

    @staticmethod
    def _current_proxy_type(proxy: dict[str, Any]) -> str:
        proxy_type = str(proxy.get("type", "http") or "http").lower()
        return proxy_type if proxy_type in {"http", "https", "socks5"} else "http"

    def _current_textual_theme_value(self) -> str:
        if self.current_textual_theme in self.textual_themes:
            return self.current_textual_theme
        return self.textual_themes[0]

    def _theme_options(self) -> tuple[tuple[str, str], ...]:
        options: list[tuple[str, str]] = []
        for path in sorted(glob(os.path.join(THEMES_DIR, "*.json"))):
            rel_path = os.path.relpath(path, ROOT_DIR).replace(os.sep, "/")
            options.append((os.path.basename(path), rel_path))
        return tuple(options) or (("Default", "resources/themes/default.json"),)

    def _current_theme_value(self, options: tuple[tuple[str, str], ...]) -> str:
        current = (
            getattr(self.settings, "theme_path", "") or "resources/themes/default.json"
        ).replace("\\", "/")
        values = {value for _, value in options}
        return current if current in values else options[0][1]
