"""Execute tools and plugins with progress indication and output capture.

The runner module abstracts over the differences between Python functions
defined in ``laitoxx.features`` and Lua plugins discovered via
``lua_engine``.  Each tool may choose to run on a background thread
(``ToolSpec.threaded``) but in a terminal environment threads merely
prevent the UI from blocking on slow operations.  Output emitted via
``print`` is captured and returned alongside the tool's return value.
"""

from __future__ import annotations

import builtins
import inspect
import io
import time
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from laitoxx.app.plugins.engine import LuaPluginMeta, run_lua_plugin
from laitoxx.app.tool_registry import ToolSpec


@dataclass(slots=True)
class ToolRunResult:
    """Structured result for one tool execution."""

    success: bool
    value: Any = None
    output: str = ""
    graph_paths: list[str] | None = None
    error: str = ""

    @property
    def graphs(self) -> list[str]:
        return self.graph_paths or []


class _InputOverride:
    """Temporarily feed canned values to legacy tools that call input()."""

    def __init__(self, value: Any):
        if isinstance(value, (list, tuple)):
            self._values = ["" if item is None else str(item) for item in value]
        else:
            self._values = ["" if value is None else str(value)]
        self._index = 0
        self._original_input = builtins.input

    def __enter__(self):
        def _fake_input(prompt: str = "") -> str:
            if self._index >= len(self._values):
                return ""
            value = self._values[self._index]
            self._index += 1
            return value

        builtins.input = _fake_input
        return self

    def __exit__(self, *_):
        builtins.input = self._original_input


def _call_accepts_argument(func: Callable) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return True
    for param in signature.parameters.values():
        if param.kind in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.VAR_POSITIONAL,
        ):
            return True
    return False


def _run_callable(func: Callable, user_input: Any, out: io.StringIO) -> Any:
    """Invoke *func* with *args* and *kwargs* while capturing stdout/stderr."""
    with redirect_stdout(out), redirect_stderr(out):
        if _call_accepts_argument(func):
            return func(user_input)
        with _InputOverride(user_input):
            return func()


def run_tool(
    console: Console,
    tool_spec: ToolSpec | None,
    plugin: LuaPluginMeta | None,
    user_input: Any = None,
    *,
    threaded: bool = False,
) -> ToolRunResult:
    """Execute a Python tool or Lua plugin and return its output.

    Parameters
    ----------
    console: Console
        Console used for rendering the spinner.
    tool_spec: ToolSpec or None
        Specification of the Python tool to run; ``None`` indicates a Lua plugin.
    plugin: LuaPluginMeta or None
        Plugin metadata when running a Lua plugin; ``None`` otherwise.
    user_input: Any
        Input value passed to the tool function or plugin.
    threaded: bool
        Run the callable in a worker thread. Keep this disabled in Textual
        because stdout/stderr capture changes process globals.

    Returns
    -------
    tuple
        ToolRunResult with success flag, captured output, return value, and any
        graph paths saved by a Lua plugin.
    """
    output_buffer = io.StringIO()
    result_holder: dict[str, Any] = {"value": None, "error": ""}
    graph_paths: list[str] = []

    def target():
        # Determine whether to run a Python tool or a Lua plugin
        try:
            if tool_spec is not None:
                func = tool_spec.func
                if tool_spec.input_type is None:
                    result_holder["value"] = _run_callable(func, None, output_buffer)
                else:
                    result_holder["value"] = _run_callable(func, user_input, output_buffer)
            else:
                if plugin is None:
                    raise ValueError("No tool or plugin was provided.")
                # Determine which function to call based on plugin type
                func_name = "search"
                if plugin and getattr(plugin, "plugin_type", None):
                    ptype = plugin.plugin_type
                    if ptype == "processor":
                        func_name = "process"
                    elif ptype == "formatter":
                        func_name = "format"
                    else:
                        func_name = "search"
                # Lua plugins accept a string argument (query or data)
                result_holder["value"] = run_lua_plugin(
                    plugin,
                    function_name=func_name,
                    query=str(user_input or ""),
                    options={},
                    output_callback=lambda msg: output_buffer.write(str(msg) + "\n"),
                    graph_callback=lambda path: graph_paths.append(path),
                )
        except Exception as e:
            result_holder["error"] = str(e)
            output_buffer.write(f"Error: {e}\n")
            result_holder["value"] = None

    thread = None
    if threaded:
        import threading

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
    else:
        target()

    with Progress(
        SpinnerColumn(style="bold green"),
        TextColumn("{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Running...", total=None)
        while True:
            if thread is not None and not thread.is_alive():
                break
            if thread is None:
                # Synchronous execution finished immediately
                break
            time.sleep(0.1)
    if thread:
        thread.join()

    captured = output_buffer.getvalue()
    error = result_holder.get("error", "")
    if not error and plugin is not None and result_holder.get("value") is None:
        lowered = captured.lower()
        if "error:" in lowered or "lua error" in lowered:
            error = captured.strip().splitlines()[-1] if captured.strip() else "Plugin failed"
    return ToolRunResult(
        success=not error,
        value=result_holder.get("value"),
        output=captured,
        graph_paths=graph_paths,
        error=error,
    )
