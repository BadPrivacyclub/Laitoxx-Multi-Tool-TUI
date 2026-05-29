"""Interactive menu for selecting tools and actions.

This module provides high–level functions to build hierarchical menus
using ``InquirerPy``.  The menu structure mirrors the GUI version of
Laitoxx: Information Gathering, Web Security, Utilities, Lua plugins,
Settings and Exit.  Each category exposes the tools defined in
``gui.tool_registry`` along with a brief description.
"""

from __future__ import annotations

import re

from InquirerPy import inquirer

from laitoxx.app.plugins.engine import LuaPluginMeta, discover_lua_plugins
from laitoxx.app.tool_registry import CATEGORIES, TOOL_REGISTRY


def main_menu() -> str:
    """Display the top–level menu and return the selected action key.

    Returns one of: ``"information_gathering"``, ``"web_security"``,
    ``"utils"``, ``"lua_plugins"``, ``"settings"`` or ``"exit"``.
    """
    choices = [
        {"name": "[/] All Tools", "value": "all_tools"},
        {"name": "[1] Information Gathering", "value": "information_gathering"},
        {"name": "[2] Web Security", "value": "web_security"},
        {"name": "[3] Utilities", "value": "utils"},
        {"name": "[4] Lua Plugins", "value": "lua_plugins"},
        {"name": "[5] Settings", "value": "settings"},
        {"name": "[6] Exit", "value": "exit"},
    ]
    result = inquirer.select(
        message="Main Menu — select a category",
        choices=choices,
        default=0,
    ).execute()
    return result


def select_tool(category_key: str) -> tuple[str | None, object | None]:
    """Prompt the user to choose a tool within a category or a Lua plugin.

    Parameters
    ----------
    category_key: str
        Key returned by ``main_menu``.

    Returns
    -------
    tuple
        A pair ``(name, ToolSpec)`` for regular tools, or ``(name, None)``
        when a Lua plugin is selected.  Returns ``(None, None)`` when
        the user opts to go back.
    """
    if category_key in ("all_tools", "information_gathering", "web_security", "utils"):
        if category_key == "all_tools":
            tool_names = [name for names in CATEGORIES.values() for name in names]
        else:
            tool_names = CATEGORIES.get(category_key, [])
        choices: list[dict[str, str]] = []
        for idx, name in enumerate(tool_names, start=1):
            spec = TOOL_REGISTRY.get(name)
            desc = spec.desc if spec else ""
            choices.append({"name": f"[{idx}] {name} — {desc}", "value": name})
        choices.append({"name": "< Back", "value": None})
        selected = _pick("Select a tool", choices)
        if not selected:
            return None, None
        return selected, TOOL_REGISTRY[selected]
    elif category_key == "lua_plugins":
        plugins = discover_lua_plugins()
        # Filter plugins for Debian support
        supported_plugins: list[LuaPluginMeta] = []
        for p in plugins:
            if plugin_supports_debian(p):
                supported_plugins.append(p)
        if not supported_plugins:
            inquirer.confirm(
                message="No compatible Lua plugins found. Press Enter to return.",
                default=True,
            ).execute()
            return None, None
        choices = [
            {"name": f"[{i}] {p.name} — {p.description}", "value": p}
            for i, p in enumerate(supported_plugins, start=1)
        ]
        choices.append({"name": "< Back", "value": None})
        selected = _pick("Select a Lua plugin", choices)
        if not selected:
            return None, None
        # Return plugin meta as the second value; name is for display
        return selected.name, selected
    else:
        # Settings and Exit don't require a tool selection
        return None, None


def _pick(message: str, choices: list[dict]) -> object:
    try:
        return inquirer.fuzzy(message=message, choices=choices).execute()
    except Exception:
        return inquirer.select(message=message, choices=choices, default=0).execute()


def plugin_supports_debian(plugin: LuaPluginMeta) -> bool:
    """Check if a Lua plugin declares support for Debian/Unix systems.

    The plugin file may optionally declare a ``supported_os`` or ``systems``
    field in its ``plugin`` table, for example::

        local plugin = {
            id = "example",
            name = "Example",
            supported_os = {"windows", "debian", "linux"},
        }

    If no such field is present the plugin is considered cross-platform.
    """
    path = plugin.filepath
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
    except Exception:
        return False
    # Search for patterns like supported_os = { "debian", "linux" }
    pattern = re.compile(r"supported_os\s*=\s*{([^}]+)}")
    m = pattern.search(src)
    if not m:
        # Fallback: check for 'systems' field
        pattern2 = re.compile(r"systems\s*=\s*{([^}]+)}")
        m = pattern2.search(src)
    if not m:
        return True  # No declaration implies cross-platform
    body = m.group(1)
    # Extract entries between quotes or bare words separated by commas
    entries = re.findall(r"[\'\"]?([A-Za-z0-9_\-]+)[\'\"]?", body)
    entries = [e.lower() for e in entries]
    # Accept 'linux' as generic; any value containing 'debian' or 'linux'
    return any(e in ("debian", "linux") for e in entries)
