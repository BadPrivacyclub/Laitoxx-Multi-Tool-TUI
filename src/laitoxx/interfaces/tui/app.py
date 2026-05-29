"""Textual based TUI for Laitoxx."""

from __future__ import annotations

import asyncio
import datetime as _dt
import io
import json
import os
import re
import sys
import webbrowser
from contextlib import suppress
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.markup import escape
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    LoadingIndicator,
    ProgressBar,
    RichLog,
    Static,
    Tree,
)

from laitoxx.app.plugins.engine import (
    apply_settings_to_plugins,
    discover_lua_plugins,
    load_lua_plugin_settings,
    save_lua_plugin_settings,
)
from laitoxx.app.plugins.leakosint_report import (
    create_leakosint_report,
    is_leakosint_plugin,
)
from laitoxx.app.tool_registry import CATEGORIES, TOOL_REGISTRY
from laitoxx.core.settings.paths import ROOT_DIR
from laitoxx.core.settings.proxy import apply_proxy_settings
from laitoxx.features.photo_geolocation.photo2geo import PROGRESS_MARKER, RESULT_MARKER
from laitoxx.shared.graph.model import Graph

from .html_report import generate_report, save_and_open
from .localization import TuiTranslator
from .models import Field, ToolItem
from .output_cleaner import normalize_output, render_output
from .responsive import detect_responsive_state
from .runner import ToolRunResult, run_tool
from .screens import OpenReportScreen, SettingsScreen, ToolInputScreen
from .terminal import reset_terminal_modes
from .theme_registry import register_laitoxx_themes
from .tool_forms import ToolFormFactory


class LaitoxxCLI(App):
    """Full-screen Textual application."""

    CSS_PATH = "laitoxx.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "run_selected", "Run"),
        ("enter", "run_selected", "Run"),
        ("/", "focus_filter", "Filter"),
        ("f", "focus_filter", "Filter"),
        ("m", "focus_menu", "Menu"),
        ("o", "focus_output", "Output"),
        ("escape", "clear_filter", "Clear"),
        ("c", "clear_filter", "Clear"),
        ("s", "save_report", "Report"),
        ("p", "plugin_settings", "Plugin"),
        ("ctrl+r", "reload_plugins", "Reload"),
        ("ctrl+comma", "settings", "Settings"),
        ("comma", "settings", "Settings"),
    ]

    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.items: list[ToolItem] = []
        self.visible_items: list[ToolItem] = []
        self.last_result = ""
        self.last_graph_paths: list[str] = []
        self.last_title = "Report"
        self.tool_running = False
        self.laitoxx_theme_names: list[str] = []
        self.phone_layout = False
        self.i18n = TuiTranslator(getattr(settings, "language", "en"))
        self.form_factory = ToolFormFactory(self.i18n.language)
        self.hub_indexes: list[dict[str, Any]] = []
        self.hub_source_path = ""
        self.photo2geo_process: asyncio.subprocess.Process | None = None
        self.photo2geo_cancel_requested = False
        self.hub_download_cancel_requested = False
        self.local_index_cancel_requested = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, id="app-header")
        with Container(id="root"):
            with Vertical(id="sidebar"):
                yield Static(self.i18n.t("brand"), id="brand")
                yield Input(placeholder=self.i18n.t("filter_placeholder"), id="filter")
                yield Tree(self.i18n.t("tools_root"), id="tool-tree")
            with Vertical(id="workbench"):
                yield Static(self.i18n.t("details_empty"), id="details")
                yield RichLog(id="output", wrap=True, markup=False, highlight=False)
                yield VerticalScroll(id="hub-index-actions")
                yield Static(self.i18n.t("ready"), id="status")
        yield Footer(id="app-footer")

    def on_mount(self) -> None:
        self.laitoxx_theme_names = register_laitoxx_themes(self)
        preferred_theme = self._preferred_textual_theme()
        if preferred_theme in self.available_themes:
            self.theme = preferred_theme
        tree = self.query_one("#tool-tree", Tree)
        tree.show_root = False
        tree.root.expand()
        filter_input = self.query_one("#filter", Input)
        output_log = self.query_one("#output", RichLog)
        output_log.border_title = self.i18n.t("output_title")
        output_log.can_focus = True
        self._apply_responsive_layout()
        self._load_items()
        self._refresh_tree()
        if self.phone_layout:
            tree.focus()
        else:
            filter_input.focus()
        self._write_welcome()

    def on_resize(self, event) -> None:
        self._apply_responsive_layout(event.size.width, event.size.height)

    def _load_items(self) -> None:
        items: list[ToolItem] = []
        for category, names in CATEGORIES.items():
            label = self._category_label(category)
            for name in names:
                spec = TOOL_REGISTRY.get(name)
                if spec:
                    items.append(ToolItem(name=name, category=label, kind="Python", spec=spec))
        plugins = discover_lua_plugins()
        with suppress(Exception):
            apply_settings_to_plugins(plugins, load_lua_plugin_settings())
        for plugin in plugins:
            if plugin.enabled:
                items.append(
                    ToolItem(
                        name=plugin.name,
                        category=self.i18n.t("lua_plugins"),
                        kind=plugin.plugin_type,
                        plugin=plugin,
                    )
                )
        self.items = items

    def _refresh_tree(self, query: str = "") -> None:
        tree = self.query_one("#tool-tree", Tree)
        tree.clear()
        tree.root.expand()
        needle = query.casefold().strip()
        self.visible_items = [
            item
            for item in self.items
            if not needle
            or needle in item.name.casefold()
            or needle in self._item_label(item).casefold()
            or needle in item.category.casefold()
        ]
        categories = list(dict.fromkeys(item.category for item in self.items))
        for category in categories:
            category_items = [item for item in self.visible_items if item.category == category]
            if not category_items:
                continue
            category_node = tree.root.add(category)
            category_node.expand()
            for item in category_items:
                category_node.add_leaf(self._item_label(item), data=item)
        self._focus_first_visible_item(tree)
        self._update_details()

    def _apply_responsive_layout(self, width: int | None = None, height: int | None = None) -> None:
        state = detect_responsive_state(width or self.size.width, height or self.size.height)
        self.phone_layout = state.phone

        for selector in (
            "#app-header",
            "#app-footer",
            "#root",
            "#sidebar",
            "#workbench",
            "#brand",
            "#filter",
            "#tool-tree",
            "#details",
            "#output",
            "#hub-index-actions",
            "#status",
        ):
            widget = self.query_one(selector)
            self._set_widget_class(widget, "compact", state.compact)
            self._set_widget_class(widget, "narrow", state.narrow)
            self._set_widget_class(widget, "micro", state.micro)
            self._set_widget_class(widget, "short", state.short)
            self._set_widget_class(widget, "phone", state.phone)

    @staticmethod
    def _set_widget_class(widget, class_name: str, enabled: bool) -> None:
        if enabled:
            widget.add_class(class_name)
        else:
            widget.remove_class(class_name)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter":
            self._refresh_tree(event.value)

    def on_tree_node_highlighted(self, _event: Tree.NodeHighlighted) -> None:
        self._update_details()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        if isinstance(event.node.data, ToolItem):
            self.action_run_selected()

    def action_focus_filter(self) -> None:
        self.query_one("#filter", Input).focus()

    def action_focus_menu(self) -> None:
        self.query_one("#tool-tree", Tree).focus()

    def action_focus_output(self) -> None:
        self.query_one("#output", RichLog).focus()

    def action_clear_filter(self) -> None:
        field = self.query_one("#filter", Input)
        field.value = ""
        if self.phone_layout:
            self.query_one("#tool-tree", Tree).focus()
        else:
            field.focus()

    def action_reload_plugins(self) -> None:
        self._load_items()
        self._refresh_tree(self.query_one("#filter", Input).value)
        self._set_status(self.i18n.t("plugins_reloaded"), "success")

    def action_settings(self) -> None:
        self.push_screen(
            SettingsScreen(
                self.settings,
                textual_themes=self.available_themes.keys(),
                current_textual_theme=str(self.theme),
            ),
            callback=self._on_settings_result,
        )

    def action_plugin_settings(self) -> None:
        item = self._selected_item()
        if item is None or item.plugin is None:
            self._set_status("Select a Lua plugin first", "info")
            return
        fields = self._lua_plugin_config_fields(item.plugin)
        if not fields:
            self._set_status("This plugin has no configurable settings", "info")
            return
        self.push_screen(
            ToolInputScreen(
                f"Settings: {item.plugin.name}",
                fields,
                language=self.i18n.language,
                submit_label=self.i18n.t("save"),
            ),
            callback=lambda data, plugin=item.plugin: self._on_plugin_settings_result(plugin, data),
        )

    def _on_plugin_settings_result(self, plugin, data: dict[str, Any] | None) -> None:
        if data is None:
            self._set_status(self.i18n.t("cancelled"), "info")
            return
        schema = self._lua_plugin_config_schema(plugin)
        config = {}
        for entry in schema:
            if not isinstance(entry, dict) or not entry.get("key"):
                continue
            key = str(entry.get("key"))
            config[key] = self._coerce_lua_config_value(
                data.get(key),
                str(entry.get("type") or "string"),
            )

        settings_data = load_lua_plugin_settings()
        plugin_settings = dict(settings_data.get(plugin.id, {}))
        plugin_settings["enabled"] = bool(getattr(plugin, "enabled", True))
        plugin_settings["config"] = config
        settings_data[plugin.id] = plugin_settings
        save_lua_plugin_settings(settings_data)
        plugin.config_values = config
        self._set_status(f"Plugin settings saved: {plugin.name}", "success")

    def _on_settings_result(self, data: dict[str, Any] | None) -> None:
        if not data:
            return
        self.settings.language = data.get("language") or self.settings.language
        self.i18n.set_language(self.settings.language)
        self.form_factory.set_language(self.settings.language)
        self.theme = data.get("tui_theme") or self.theme
        with suppress(Exception):
            self.settings.tui_theme = str(self.theme)
        self.settings.theme_path = data.get("theme_path") or self.settings.theme_path
        proxy = self._clean_proxy_settings(data.get("proxy"))
        self.settings.proxy = proxy
        with suppress(Exception):
            apply_proxy_settings(proxy)
        self._load_items()
        self._refresh_tree(self.query_one("#filter", Input).value)
        self.query_one("#brand", Static).update(self.i18n.t("brand"))
        self.query_one("#filter", Input).placeholder = self.i18n.t("filter_placeholder")
        self.query_one("#output", RichLog).border_title = self.i18n.t("output_title")
        self._set_status(self.i18n.t("settings_saved"), "success")

    @staticmethod
    def _clean_proxy_settings(proxy: Any) -> dict[str, Any]:
        if not isinstance(proxy, dict):
            proxy = {}
        proxy_type = str(proxy.get("type", "http") or "http").lower()
        if proxy_type not in {"http", "https", "socks5"}:
            proxy_type = "http"
        return {
            "enabled": bool(proxy.get("enabled", False)),
            "type": proxy_type,
            "host": str(proxy.get("host", "") or "").strip(),
            "port": str(proxy.get("port", "") or "").strip(),
            "username": str(proxy.get("username", "") or "").strip(),
            "password": str(proxy.get("password", "") or ""),
        }

    def _lua_plugin_config_fields(self, plugin) -> list[Field]:
        fields: list[Field] = []
        current_values = getattr(plugin, "config_values", {}) or {}
        for entry in self._lua_plugin_config_schema(plugin):
            if not isinstance(entry, dict) or not entry.get("key"):
                continue
            key = str(entry.get("key"))
            field_type = str(entry.get("type") or "string").lower()
            default = current_values.get(key, entry.get("default", ""))
            if field_type == "boolean":
                fields.append(
                    Field(
                        name=key,
                        label=str(entry.get("label") or key),
                        kind="bool",
                        default=bool(default),
                    )
                )
            else:
                fields.append(
                    Field(
                        name=key,
                        label=str(entry.get("label") or key),
                        default="" if default is None else default,
                    )
                )
        return fields

    @staticmethod
    def _lua_plugin_config_schema(plugin) -> list[dict[str, Any]]:
        raw = getattr(plugin, "config_schema", None)
        if not raw:
            return []
        if isinstance(raw, list):
            return [entry for entry in raw if isinstance(entry, dict)]
        try:
            from laitoxx.app.plugins.engine import _lua_table_to_python

            converted = _lua_table_to_python(raw)
        except Exception:
            return []
        if isinstance(converted, list):
            return [entry for entry in converted if isinstance(entry, dict)]
        return []

    @staticmethod
    def _coerce_lua_config_value(value: Any, field_type: str) -> Any:
        if field_type.lower() == "boolean":
            return bool(value)
        if field_type.lower() == "number":
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0
        return "" if value is None else str(value)

    def action_run_selected(self) -> None:
        if self.tool_running:
            self._set_status(self.i18n.t("tool_already_running"), "running")
            return
        item = self._selected_item()
        if item is None:
            self._set_status(self.i18n.t("no_tool_selected"), "error")
            return
        fields = self.form_factory.fields_for_item(item)
        if fields:
            field_resolver = None
            if item.spec is not None and item.spec.input_type == "photo2geo":

                def resolve_photo2geo_fields(data: dict[str, Any]):
                    return self.form_factory.fields_for_item(item, data)

                field_resolver = resolve_photo2geo_fields
            self.push_screen(
                ToolInputScreen(
                    self._item_label(item),
                    fields,
                    field_resolver=field_resolver,
                    language=self.i18n.language,
                ),
                callback=lambda data, item=item: self._on_tool_input(item, data),
            )
            return
        self._on_tool_input(item, {})

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id or ""
        if button_id == "hub-download-cancel":
            event.stop()
            self._cancel_hub_download()
            return
        if button_id == "index-create-cancel":
            event.stop()
            self._cancel_local_index_creation()
            return
        if button_id == "hub-download-all":
            event.stop()
            self._start_hub_download(
                [str(index["repo_id"]) for index in self.hub_indexes if index.get("repo_id")]
            )
            return
        if button_id.startswith("hub-download-"):
            event.stop()
            try:
                index = int(button_id.removeprefix("hub-download-"))
                repo_id = str(self.hub_indexes[index]["repo_id"])
            except (IndexError, KeyError, ValueError):
                return
            self._start_hub_download([repo_id])

    def _on_tool_input(self, item: ToolItem, data: dict[str, Any] | None) -> None:
        if data is None:
            self._set_status(self.i18n.t("cancelled"), "info")
            return
        self.run_worker(
            self._run_item_flow(item, data),
            exclusive=True,
            description=self.i18n.t("run_worker", name=self._item_label(item)),
        )

    async def _run_item_flow(self, item: ToolItem, data: dict[str, Any]) -> None:
        user_input = self.form_factory.build_input(item, data)
        self._clear_hub_index_actions()
        local_index_task = (
            item.name == "Photo geolocation"
            and isinstance(user_input, dict)
            and user_input.get("task") == "create_index"
        )
        photo_activity_task = item.name == "Photo geolocation" and not local_index_task
        if local_index_task:
            self.photo2geo_cancel_requested = False
            self.local_index_cancel_requested = False
            self._show_local_index_progress(user_input)
            await asyncio.sleep(0)
        elif photo_activity_task:
            self._show_photo2geo_activity(user_input if isinstance(user_input, dict) else {})
            await asyncio.sleep(0)
        item_label = self._item_label(item)
        self._set_status(self.i18n.t("running_tool", name=item_label), "running")
        self.tool_running = True
        try:
            if item.name == "Photo geolocation":
                run_result = await self._execute_photo2geo_isolated(
                    user_input,
                    progress_handler=self._update_local_index_progress
                    if local_index_task
                    else None,
                )
            else:
                await asyncio.sleep(0)
                if item.plugin is not None:
                    run_result = await asyncio.to_thread(self._execute_item, item, user_input)
                else:
                    # Legacy tools still use global stdout capture; keep them sync.
                    run_result = self._execute_item(item, user_input)
        except Exception as exc:
            self._show_result(item_label, f"Error: {exc}")
            self._set_status(self.i18n.t("tool_failed", name=item_label), "error")
            if local_index_task:
                self._finish_local_index_progress(
                    self.i18n.t("index_creation_failed"), success=False
                )
            elif photo_activity_task:
                self._finish_photo2geo_activity(self.i18n.t("photo_failed"), success=False)
            self.tool_running = False
            return
        self.tool_running = False
        self.last_title = item_label
        self.last_result = run_result.output or (
            "" if run_result.value is None else str(run_result.value)
        )
        self.last_graph_paths = run_result.graphs
        self._show_result(item_label, self.last_result)
        await self._maybe_offer_leakosint_report(item, user_input, run_result)
        if (
            item.name == "Photo geolocation"
            and user_input.get("task") == "hub_search"
            and run_result.success
        ):
            value = run_result.value if isinstance(run_result.value, dict) else {}
            indexes = value.get("indexes", [])
            if isinstance(indexes, list):
                self._show_hub_index_actions(indexes, str(user_input.get("source_path") or ""))
        if local_index_task:
            if self.local_index_cancel_requested:
                self._set_status(self.i18n.t("local_index_cancelled"), "info")
                self._finish_local_index_progress(
                    self.i18n.t("index_creation_cancelled"), success=False
                )
                return
            self._finish_local_index_progress(
                self.i18n.t("local_index_ready")
                if run_result.success
                else self.i18n.t("index_creation_failed"),
                success=run_result.success,
            )
        elif photo_activity_task:
            self._finish_photo2geo_activity(
                self.i18n.t("photo_completed")
                if run_result.success
                else self.i18n.t("photo_failed"),
                success=run_result.success,
            )
        if run_result.success:
            self._set_status(self.i18n.t("tool_completed", name=item_label), "success")
        else:
            self._set_status(self.i18n.t("tool_failed", name=item_label), "error")

    def _execute_item(self, item: ToolItem, user_input: Any):
        console = Console(file=io.StringIO(), force_terminal=False, width=120)
        return run_tool(console, item.spec, item.plugin, user_input, threaded=False)

    async def _maybe_offer_leakosint_report(
        self, item: ToolItem, user_input: Any, run_result: ToolRunResult
    ) -> None:
        if item.plugin is None or not run_result.success or not is_leakosint_plugin(item.plugin):
            return
        result_text = str(run_result.value or self.last_result or run_result.output or "")
        try:
            report_path = await asyncio.to_thread(
                create_leakosint_report,
                result_text,
                graph_paths=run_result.graphs,
                query=str(user_input or ""),
            )
        except Exception as exc:
            self._append_output(f"\n[Report error] {exc}")
            return
        if not report_path:
            return
        self._append_output(f"\n[Report] {report_path}")
        self._set_status(self.i18n.t("leak_report_saved", path=report_path), "success")
        self.push_screen(
            OpenReportScreen(
                self.i18n.t("leak_report_title"),
                report_path,
                language=self.i18n.language,
            ),
            callback=lambda open_report, path=report_path: self._open_report_choice(
                path, bool(open_report)
            ),
        )

    def _open_report_choice(self, path: str, open_report: bool) -> None:
        if not open_report:
            return
        with suppress(Exception):
            webbrowser.open(Path(path).resolve().as_uri())

    async def _execute_photo2geo_isolated(
        self,
        user_input: Any,
        progress_handler: Any = None,
    ) -> ToolRunResult:
        project_root = ROOT_DIR
        env = os.environ.copy()
        env.setdefault("PYTHONIOENCODING", "utf-8")
        src_dir = str(ROOT_DIR / "src")
        env["PYTHONPATH"] = (
            src_dir
            if not env.get("PYTHONPATH")
            else src_dir + os.pathsep + str(env["PYTHONPATH"])
        )
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-X",
            "utf8",
            "-m",
            "laitoxx.features.photo_geolocation.photo2geo",
            "--config-json",
            json.dumps(user_input or {}, ensure_ascii=False),
            "--emit-result-json",
            cwd=project_root,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        if progress_handler is None:
            stdout, _ = await process.communicate()
            raw_output = stdout.decode("utf-8", errors="replace") if stdout else ""
        else:
            self.photo2geo_process = process
            if self.photo2geo_cancel_requested:
                with suppress(ProcessLookupError):
                    process.terminate()
            output_lines = []
            try:
                while process.stdout is not None:
                    raw_line = await process.stdout.readline()
                    if not raw_line:
                        break
                    line = raw_line.decode("utf-8", errors="replace")
                    if line.startswith(PROGRESS_MARKER):
                        with suppress(json.JSONDecodeError):
                            progress_handler(json.loads(line[len(PROGRESS_MARKER) :]))
                        continue
                    output_lines.append(line)
                await process.wait()
            finally:
                if self.photo2geo_process is process:
                    self.photo2geo_process = None
            raw_output = "".join(output_lines)
        output, value = self._parse_photo2geo_result(raw_output)
        return ToolRunResult(
            success=process.returncode == 0,
            value=value,
            output=output,
            error=""
            if process.returncode == 0
            else f"Photo geolocation exited with {process.returncode}",
        )

    @staticmethod
    def _parse_photo2geo_result(output: str) -> tuple[str, Any]:
        value = None
        visible_lines = []
        for line in output.splitlines(keepends=True):
            if line.startswith(RESULT_MARKER):
                with suppress(json.JSONDecodeError):
                    value = json.loads(line[len(RESULT_MARKER) :])
                continue
            visible_lines.append(line)
        return "".join(visible_lines), value

    def _show_photo2geo_activity(self, config: dict[str, Any]) -> None:
        actions = self.query_one("#hub-index-actions", VerticalScroll)
        actions.remove_children()
        actions.add_class("visible")
        engine = str(config.get("engine") or "netryx")
        task = str(config.get("task") or "check_setup")
        title = (
            self.i18n.t("photo_title_geoclip")
            if engine == "geoclip"
            else self.i18n.t("photo_title_netryx")
        )
        if task == "hub_search":
            title = self.i18n.t("photo_title_hub_search")
        elif task in {"import_index", "export_index"}:
            title = self.i18n.t("photo_title_index_io")
        actions.mount(
            Vertical(
                Horizontal(
                    LoadingIndicator(id="photo2geo-activity-spinner"),
                    Static(title, id="photo2geo-activity-title"),
                    classes="photo2geo-activity-header",
                ),
                Static(self.i18n.t("worker_running"), id="photo2geo-activity-stats"),
                id="photo2geo-activity",
            )
        )

    def _finish_photo2geo_activity(self, message: str, *, success: bool) -> None:
        if len(self.query("#photo2geo-activity")) == 0:
            return
        with suppress(Exception):
            self.query_one("#photo2geo-activity-spinner", LoadingIndicator).add_class("finished")
            self.query_one("#photo2geo-activity-title", Static).update(message)
            self.query_one("#photo2geo-activity-stats", Static).update(
                self.i18n.t("completed") if success else self.i18n.t("stopped_error")
            )

    def _show_hub_index_actions(self, indexes: list[Any], source_path: str) -> None:
        actions = self.query_one("#hub-index-actions", VerticalScroll)
        actions.remove_children()
        self.hub_indexes = [
            index
            for index in indexes[:50]
            if isinstance(index, dict) and str(index.get("repo_id") or "").strip()
        ]
        self.hub_source_path = source_path
        if not self.hub_indexes:
            actions.remove_class("visible")
            return

        actions.add_class("visible")
        actions.mount(
            Horizontal(
                Static(self.i18n.t("community_indexes"), classes="hub-index-heading"),
                Button(self.i18n.t("download_all"), id="hub-download-all", variant="success"),
                classes="hub-index-header",
            )
        )
        for position, index in enumerate(self.hub_indexes):
            repo_id = str(index["repo_id"])
            name = str(index.get("name") or self.i18n.t("unknown"))
            entries = str(index.get("num_entries") or "?")
            summary = f"{name} | repo={repo_id} | entries={entries}"
            actions.mount(
                Horizontal(
                    Static(summary, markup=False, classes="hub-index-summary"),
                    Button(self.i18n.t("download"), id=f"hub-download-{position}"),
                    classes="hub-index-row",
                )
            )
        actions.mount(self._hub_download_progress_widget())

    def _clear_hub_index_actions(self) -> None:
        actions = self.query_one("#hub-index-actions", VerticalScroll)
        actions.remove_children()
        actions.remove_class("visible")
        self.hub_indexes = []
        self.hub_source_path = ""

    def _start_hub_download(self, repo_ids: list[str]) -> None:
        if self.tool_running or not repo_ids:
            return
        self.photo2geo_cancel_requested = False
        self.hub_download_cancel_requested = False
        self._show_hub_download_progress(repo_ids)
        self.tool_running = True
        self.run_worker(
            self._run_hub_download(repo_ids),
            exclusive=True,
            description=self.i18n.t("download"),
        )

    async def _run_hub_download(self, repo_ids: list[str]) -> None:
        config: dict[str, Any] = {
            "task": "hub_download_all" if len(repo_ids) > 1 else "hub_download",
            "source_path": self.hub_source_path,
        }
        if len(repo_ids) > 1:
            config["repo_ids"] = repo_ids
        else:
            config["repo_id"] = repo_ids[0]
        repo_sizes = {
            str(index["repo_id"]): index["file_size_bytes"]
            for index in self.hub_indexes
            if index.get("repo_id") in repo_ids and index.get("file_size_bytes")
        }
        if repo_sizes:
            config["repo_sizes"] = repo_sizes
        self._set_status(self.i18n.t("downloading_index"), "running")
        self.tool_running = True
        try:
            result = await self._execute_photo2geo_isolated(
                config,
                progress_handler=self._update_hub_download_progress,
            )
        except Exception as exc:
            self._show_result("Photo geolocation", f"Error: {exc}")
            self._set_status(self.i18n.t("photo_download_failed"), "error")
            self._finish_hub_download_progress(self.i18n.t("download_failed"), success=False)
            self.tool_running = False
            return
        self.tool_running = False
        if self.hub_download_cancel_requested:
            self._set_status(self.i18n.t("download_cancelled"), "info")
            self._finish_hub_download_progress(self.i18n.t("download_cancelled"), success=False)
            return
        self.last_title = "Photo geolocation"
        self.last_result = result.output or ("" if result.value is None else str(result.value))
        self._show_result(self.last_title, self.last_result)
        if result.success:
            self._set_status(self.i18n.t("download_completed"), "success")
            self._finish_hub_download_progress(self.i18n.t("download_completed"), success=True)
        else:
            self._set_status(self.i18n.t("download_failed"), "error")
            self._finish_hub_download_progress(self.i18n.t("download_failed"), success=False)

    def _show_hub_download_progress(self, repo_ids: list[str]) -> None:
        actions = self.query_one("#hub-index-actions", VerticalScroll)
        for button in actions.query("Button"):
            button.disabled = True
        progress_panel = self.query_one("#hub-download-progress", Vertical)
        progress_panel.remove_class("hidden")
        self.query_one("#hub-download-spinner", LoadingIndicator).remove_class("finished")
        self.query_one("#hub-download-progress-title", Static).update(
            self.i18n.t("preparing_download_count", count=len(repo_ids))
        )
        self.query_one("#hub-download-progress-bar", ProgressBar).update(total=None, progress=0)
        self.query_one("#hub-download-progress-stats", Static).update(
            self.i18n.t("waiting_for_data")
        )
        self.query_one("#hub-download-cancel", Button).disabled = False

    def _hub_download_progress_widget(self) -> Vertical:
        return Vertical(
            Horizontal(
                LoadingIndicator(id="hub-download-spinner"),
                Static(self.i18n.t("preparing_download"), id="hub-download-progress-title"),
                Button(self.i18n.t("cancel"), id="hub-download-cancel", variant="error"),
                classes="hub-download-progress-header",
            ),
            ProgressBar(total=None, show_eta=False, id="hub-download-progress-bar"),
            Static(self.i18n.t("waiting_for_data"), id="hub-download-progress-stats"),
            id="hub-download-progress",
            classes="hidden",
        )

    def _update_hub_download_progress(self, event: dict[str, Any]) -> None:
        if len(self.query("#hub-download-progress")) == 0:
            return
        title = self.query_one("#hub-download-progress-title", Static)
        stats = self.query_one("#hub-download-progress-stats", Static)
        progress = self.query_one("#hub-download-progress-bar", ProgressBar)
        phase = str(event.get("phase") or "")
        repo_id = str(event.get("repo_id") or "")
        position = int(event.get("index") or 1)
        count = int(event.get("count") or 1)
        if phase == "downloading":
            downloaded = int(event.get("downloaded_bytes") or 0)
            total = event.get("total_bytes")
            total_int = int(total) if total else None
            speed = float(event.get("speed_bps") or 0)
            eta = event.get("eta_seconds")
            progress.update(total=total_int, progress=downloaded)
            title.update(
                self.i18n.t("download_title", position=position, count=count, repo_id=repo_id)
            )
            remaining = self._format_duration(float(eta)) if eta is not None else "--"
            size_text = (
                f"{self._format_bytes(downloaded)} / {self._format_bytes(total_int)}"
                if total_int
                else self._format_bytes(downloaded)
            )
            stats.update(
                f"{size_text} | {self._format_bytes(speed)}/s | "
                f"{self.i18n.t('remaining')} {remaining}"
            )
            if not self.hub_download_cancel_requested:
                self.query_one("#hub-download-cancel", Button).disabled = False
            return
        if phase == "extracting":
            title.update(
                self.i18n.t("unpacking_title", position=position, count=count, repo_id=repo_id)
            )
            stats.update(str(event.get("message") or self.i18n.t("extracting_index")))
            return
        if phase == "installing":
            title.update(self.i18n.t("installing_downloaded_index"))
            stats.update(
                f"{event.get('message') or self.i18n.t('installing_index')}; "
                f"{self.i18n.t('cancellation_unavailable')}"
            )
            self.query_one("#hub-download-cancel", Button).disabled = True
            return
        title.update(self.i18n.t("download_title", position=position, count=count, repo_id=repo_id))
        stats.update(str(event.get("message") or self.i18n.t("downloading_unknown_size")))

    def _cancel_hub_download(self) -> None:
        if not self.tool_running:
            return
        self.photo2geo_cancel_requested = True
        self.hub_download_cancel_requested = True
        self._set_status(self.i18n.t("download_cancel_status"), "running")
        with suppress(Exception):
            self.query_one("#hub-download-progress-title", Static).update(
                self.i18n.t("download_cancel_title")
            )
            self.query_one("#hub-download-cancel", Button).disabled = True
        if self.photo2geo_process is not None:
            with suppress(ProcessLookupError):
                self.photo2geo_process.terminate()

    def _finish_hub_download_progress(self, message: str, *, success: bool) -> None:
        if len(self.query("#hub-download-progress")) == 0:
            return
        self.query_one("#hub-download-spinner", LoadingIndicator).add_class("finished")
        self.query_one("#hub-download-progress-title", Static).update(message)
        self.query_one("#hub-download-cancel", Button).disabled = True
        if success:
            progress = self.query_one("#hub-download-progress-bar", ProgressBar)
            progress.update(total=100, progress=100)
        for button in self.query_one("#hub-index-actions", VerticalScroll).query("Button"):
            if button.id != "hub-download-cancel":
                button.disabled = False

    def _show_local_index_progress(self, config: dict[str, Any]) -> None:
        actions = self.query_one("#hub-index-actions", VerticalScroll)
        actions.remove_children()
        actions.add_class("visible")
        area = self.i18n.t(
            "local_index_area",
            lat=config.get("center_lat", "?"),
            lon=config.get("center_lon", "?"),
            radius=config.get("radius_km", "1"),
            grid=config.get("grid_resolution", "300"),
        )
        actions.mount(
            Vertical(
                Horizontal(
                    LoadingIndicator(id="index-create-spinner"),
                    Static(self.i18n.t("preparing_local_index"), id="index-create-progress-title"),
                    Button(self.i18n.t("cancel"), id="index-create-cancel", variant="error"),
                    classes="hub-download-progress-header",
                ),
                ProgressBar(total=None, show_eta=False, id="index-create-progress-bar"),
                Static(self.i18n.t("street_view_scan_start"), id="index-create-progress-stats"),
                Static(area, id="index-create-area"),
                id="index-create-progress",
            )
        )

    def _update_local_index_progress(self, event: dict[str, Any]) -> None:
        if len(self.query("#index-create-progress-title")) == 0:
            return
        title = self.query_one("#index-create-progress-title", Static)
        stats = self.query_one("#index-create-progress-stats", Static)
        progress = self.query_one("#index-create-progress-bar", ProgressBar)
        cancel = self.query_one("#index-create-cancel", Button)
        stage = str(event.get("stage") or "")
        if stage in {"scan", "panoramas"}:
            completed = int(event.get("progress") or 0)
            total = int(event.get("total") or 0)
            unit = str(event.get("unit") or "items")
            speed = float(event.get("speed_per_second") or 0)
            eta = event.get("eta_seconds")
            progress.update(total=total or None, progress=completed)
            title.update(
                self.i18n.t("scan_coverage")
                if stage == "scan"
                else self.i18n.t("download_extract_descriptors")
            )
            remaining = self._format_duration(float(eta)) if eta is not None else "--"
            stats.update(
                f"{completed:,} / {total:,} {unit} | {speed:.2f}/s | remaining {remaining}"
            )
            if not self.local_index_cancel_requested:
                cancel.disabled = False
            return
        if stage == "building":
            title.update(self.i18n.t("building_index"))
            stats.update(str(event.get("message") or self.i18n.t("fitting_index")))
            cancel.disabled = True
            return
        if stage == "complete":
            title.update(self.i18n.t("local_index_ready"))
            stats.update(str(event.get("message") or self.i18n.t("index_created")))
            cancel.disabled = True
            return
        stats.update(str(event.get("message") or self.i18n.t("preparing_index_creation")))

    def _cancel_local_index_creation(self) -> None:
        if not self.tool_running:
            return
        self.photo2geo_cancel_requested = True
        self.local_index_cancel_requested = True
        self._set_status(self.i18n.t("local_index_cancel_status"), "running")
        with suppress(Exception):
            self.query_one("#index-create-progress-title", Static).update(
                self.i18n.t("local_index_cancel_title")
            )
            self.query_one("#index-create-cancel", Button).disabled = True
        if self.photo2geo_process is not None:
            with suppress(ProcessLookupError):
                self.photo2geo_process.terminate()

    def _finish_local_index_progress(self, message: str, *, success: bool) -> None:
        if len(self.query("#index-create-progress-title")) == 0:
            return
        self.query_one("#index-create-spinner", LoadingIndicator).add_class("finished")
        self.query_one("#index-create-progress-title", Static).update(message)
        self.query_one("#index-create-cancel", Button).disabled = True
        if success:
            self.query_one("#index-create-progress-bar", ProgressBar).update(
                total=100, progress=100
            )

    @staticmethod
    def _format_bytes(value: float | int) -> str:
        size = float(value)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024 or unit == "GB":
                return f"{size:.1f} {unit}" if unit != "B" else f"{size:.0f} B"
            size /= 1024
        return f"{size:.1f} GB"

    @staticmethod
    def _format_duration(seconds: float) -> str:
        remaining = max(0, int(round(seconds)))
        minutes, seconds = divmod(remaining, 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours:d}:{minutes:02d}:{seconds:02d}"
        return f"{minutes:02d}:{seconds:02d}"

    def _show_result(self, title: str, content: str) -> None:
        log = self.query_one("#output", RichLog)
        log.clear()
        log.border_title = self.i18n.t("output_title")
        normalized = normalize_output(content or self.i18n.t("done"))
        self.last_result = normalized
        log.write(render_output(content or self.i18n.t("done")))

    def action_save_report(self) -> None:
        if not self.last_result:
            self._set_status(self.i18n.t("no_result_to_save"), "error")
            return
        graph_obj = None
        if self.last_graph_paths:
            try:
                graph_obj = Graph.load_json(self.last_graph_paths[0])
            except Exception:
                graph_obj = None
        timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self._safe_report_filename(timestamp, self.last_title)
        html = generate_report(self.last_title, self.last_result, graph=graph_obj)
        path = save_and_open(html, filename)
        self._set_status(self.i18n.t("report_saved", path=path), "success")

    @staticmethod
    def _safe_report_filename(timestamp: str, title: str) -> str:
        safe_title = re.sub(r"[^A-Za-z0-9_.-]", "_", title.strip().replace(" ", "_"))
        safe_title = safe_title.strip("._") or "report"
        return f"{timestamp}_{safe_title[:80]}.html"

    def _selected_item(self) -> ToolItem | None:
        node = self.query_one("#tool-tree", Tree).cursor_node
        return node.data if isinstance(node.data, ToolItem) else None

    @staticmethod
    def _focus_first_visible_item(tree: Tree) -> None:
        for category_node in tree.root.children:
            if category_node.children:
                tree.move_cursor(category_node.children[0])
                return

    def _update_details(self) -> None:
        item = self._selected_item()
        if item is None:
            self.query_one("#details", Static).update(self.i18n.t("no_matching_tools"))
            return
        desc = item.spec.desc if item.spec else item.plugin.description if item.plugin else ""
        body = Table.grid(expand=True)
        body.add_column("name", ratio=2)
        body.add_column("category", ratio=1)
        body.add_column("kind", ratio=1)
        body.add_row(
            f"[bold]{escape(self._item_label(item))}[/]",
            f"[dim]{self.i18n.t('category')}[/]\n{item.category}",
            f"[dim]{self.i18n.t('type')}[/]\n{item.kind}",
        )
        body.add_row(f"[dim]{escape(desc or self.i18n.t('no_description'))}[/]", "", "")
        self.query_one("#details", Static).update(body)

    def _write_welcome(self) -> None:
        log = self.query_one("#output", RichLog)
        log.border_title = self.i18n.t("output_title")
        if self.phone_layout:
            self._append_output(self.i18n.t("welcome_phone"))
        else:
            self._append_output(self.i18n.t("welcome_desktop"))

    def _append_output(self, renderable) -> None:
        self.query_one("#output", RichLog).write(renderable)

    def _set_status(self, text: str, state: str = "info") -> None:
        status = self.query_one("#status", Static)
        status.remove_class("running", "success", "error", "info")
        status.add_class(state if state in {"running", "success", "error", "info"} else "info")
        status.update(text)

    def _category_label(self, key: str) -> str:
        return self.i18n.category(key)

    def _item_label(self, item: ToolItem) -> str:
        if item.plugin is not None:
            return item.name
        return self.i18n.tool_name(item.name)

    def _preferred_textual_theme(self) -> str:
        configured = getattr(self.settings, "tui_theme", "")
        if configured:
            return configured
        basename = os.path.splitext(os.path.basename(getattr(self.settings, "theme_path", "")))[0]
        candidate = "laitoxx-" + basename.lower().replace("_", "-").replace(" ", "-")
        if candidate in self.available_themes:
            return candidate
        if "laitoxx-soft-neon" in self.available_themes:
            return "laitoxx-soft-neon"
        return "textual-dark"


class TUIApp:
    """Compatibility wrapper used by cli.py."""

    def __init__(self, settings, console: Console | None = None):
        self.settings = settings
        self.console = console

    def run(self) -> None:
        try:
            LaitoxxCLI(self.settings).run()
        finally:
            reset_terminal_modes()
