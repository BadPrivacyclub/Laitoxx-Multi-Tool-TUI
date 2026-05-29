"""Input collectors for tools that need structured parameters in the TUI."""

from __future__ import annotations

import hashlib
from typing import Any

from InquirerPy import inquirer

from laitoxx.app.tool_registry import ToolSpec

_CANCEL = object()


def _text(message: str, default: str = "") -> str:
    return inquirer.text(message=message, default=default).execute()


def _select(message: str, choices: list[dict[str, Any]], default: Any = None) -> Any:
    kwargs: dict[str, Any] = {"message": message, "choices": choices}
    if default is not None:
        kwargs["default"] = default
    return inquirer.select(**kwargs).execute()


def _fuzzy_select(message: str, choices: list[dict[str, Any]], default: Any = None) -> Any:
    kwargs: dict[str, Any] = {"message": message, "choices": choices}
    if default is not None:
        kwargs["default"] = default
    try:
        return inquirer.fuzzy(**kwargs).execute()
    except Exception:
        return _select(message, choices, default)


def _confirm(message: str, default: bool = False) -> bool:
    return bool(inquirer.confirm(message=message, default=default).execute())


def _int(message: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
    while True:
        raw = _text(message, str(default)).strip()
        try:
            value = int(raw or default)
        except ValueError:
            continue
        if minimum is not None and value < minimum:
            continue
        if maximum is not None and value > maximum:
            continue
        return value


def _multi_text(message: str) -> str:
    lines: list[str] = []
    print(f"{message} Finish with a single END line.")
    while True:
        line = input()
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines)


def _collect_google_osint() -> dict[str, Any]:
    mode = _select(
        "Google OSINT mode",
        [
            {"name": "Manual dork query", "value": "manual"},
            {"name": "Build query from operators", "value": "builder"},
        ],
        default="manual",
    )
    engines = inquirer.checkbox(
        message="Search engines",
        choices=[
            {"name": "Google", "value": "google", "enabled": True},
            {"name": "Bing", "value": "bing"},
            {"name": "DuckDuckGo", "value": "duckduckgo"},
            {"name": "Yandex", "value": "yandex"},
        ],
    ).execute() or ["google"]
    if mode == "manual":
        return {"query": _text("Dork query:"), "engines": engines}

    base_query = _text("Base search terms (optional):")
    operator_choices = [
        "site",
        "inurl",
        "intext",
        "intitle",
        "filetype",
        "ext",
        "after",
        "before",
        "cache",
        "related",
        "info",
        "link",
        "allinurl",
        "allintitle",
        "allintext",
        "define",
        "custom",
    ]
    selected = inquirer.checkbox(
        message="Operators",
        choices=[{"name": op, "value": op} for op in operator_choices],
    ).execute()
    operators: list[tuple[str, str]] = []
    for op in selected:
        if op == "custom":
            custom = _text("Custom operator/query part:")
            if custom:
                operators.append(("custom", custom))
            continue
        value = _text(f"Value for {op}:")
        if value:
            operators.append((op, value))
    return {"base_query": base_query, "operators": operators, "engines": engines}


def _collect_telegram() -> dict[str, str]:
    method = _select(
        "Telegram search type",
        [
            {"name": "Username", "value": "TelegramUsername"},
            {"name": "Channel", "value": "TelegramChannel"},
            {"name": "Chat", "value": "TelegramChat"},
            {"name": "Parse channel", "value": "TelegramCParser"},
            {"name": "Telegram ID", "value": "TelegramID"},
        ],
        default="TelegramUsername",
    )
    return {"method": method, "query": _text("Query / @username:")}


def _collect_hash(tool_name: str) -> dict[str, Any]:
    if tool_name == "Text Hasher":
        return {
            "text": _text("Text to hash:"),
            "algorithm": _collect_hash_algorithm("sha256"),
        }
    if tool_name == "Hash Identifier":
        return {"hash": _text("Hash string:")}
    return {
        "charset": _text("Charset:", "abcdefghijklmnopqrstuvwxyz0123456789"),
        "algorithm": _collect_hash_algorithm("md5"),
        "chain_length": _int("Chain length:", 1000, minimum=1),
        "num_chains": _int("Number of chains:", 10000, minimum=1),
        "password_len": _int("Password length:", 6, minimum=1),
        "output_file": _text("Output CSV file:", "rainbow_table.csv"),
        "use_salt": _confirm("Use salt?", False),
        "salt_length": _int("Salt length:", 8, minimum=1),
    }


def _collect_hash_algorithm(default: str) -> str:
    common = [
        "sha256",
        "sha512",
        "sha1",
        "md5",
        "sha224",
        "sha384",
        "blake2b",
        "blake2s",
        "sha3_256",
        "sha3_512",
    ]
    available = sorted(str(name).lower() for name in hashlib.algorithms_available)
    ordered = [name for name in common if name in available]
    ordered.extend(name for name in available if name not in ordered)
    choices = [{"name": name, "value": name} for name in ordered]
    choices.append({"name": "Custom...", "value": "__custom__"})
    selected = _fuzzy_select("Algorithm:", choices, default=default)
    if selected == "__custom__":
        return _text("Custom algorithm:", default).strip().lower() or default
    return str(selected or default).strip().lower()


def _collect_jwt() -> dict[str, str]:
    mode = _select(
        "JWT mode",
        [
            {"name": "Analyze token", "value": "analyze"},
            {"name": "Crack HMAC secret with wordlist", "value": "crack"},
        ],
        default="analyze",
    )
    data = {"mode": mode, "token": _text("JWT token:")}
    if mode == "crack":
        data["wordlist"] = _text("Wordlist path:")
    return data


def _collect_web_security() -> dict[str, str]:
    check = _select(
        "Web security check",
        [
            {"name": "All checks", "value": "all"},
            {"name": "SSL/TLS", "value": "ssl"},
            {"name": "CORS", "value": "cors"},
            {"name": "Open Redirect", "value": "redirect"},
            {"name": "Security Headers", "value": "headers"},
        ],
        default="all",
    )
    return {"check": check, "url": _text("Target URL:")}


def _collect_text_transformer() -> dict[str, Any]:
    mode = _select(
        "Transform mode",
        [
            {"name": name, "value": name}
            for name in [
                "leet",
                "morse",
                "binary",
                "hex",
                "rot13",
                "caesar",
                "base64",
                "url",
                "reverse",
                "upper",
                "lower",
            ]
        ],
        default="base64",
    )
    action = "encode"
    if mode in {"leet", "morse", "binary", "hex", "caesar", "base64", "url"}:
        action = _select(
            "Action",
            [{"name": "Encode", "value": "encode"}, {"name": "Decode", "value": "decode"}],
            default="encode",
        )
    shift = _int("Caesar shift:", 3, minimum=1, maximum=25) if mode == "caesar" else 3
    return {"mode": mode, "action": action, "shift": shift, "text": _text("Text:")}


def _collect_password_gen() -> dict[str, Any]:
    custom_chars = _text("Only these chars (optional):")
    use_presets = not bool(custom_chars)
    return {
        "length": _int("Length:", 16, minimum=1),
        "count": _int("Count:", 1, minimum=1, maximum=100),
        "custom_chars": custom_chars,
        "use_upper": _confirm("Include uppercase?", True) if use_presets else False,
        "use_lower": _confirm("Include lowercase?", True) if use_presets else False,
        "use_digits": _confirm("Include digits?", True) if use_presets else False,
        "use_symbols": _confirm("Include symbols?", True) if use_presets else False,
        "exclude_chars": _text("Exclude chars (optional):"),
    }


def _collect_regex() -> dict[str, Any]:
    flags = inquirer.checkbox(
        message="Regex flags",
        choices=[
            {"name": "IGNORECASE", "value": "IGNORECASE"},
            {"name": "MULTILINE", "value": "MULTILINE"},
            {"name": "DOTALL", "value": "DOTALL"},
            {"name": "VERBOSE", "value": "VERBOSE"},
            {"name": "ASCII", "value": "ASCII"},
        ],
    ).execute()
    return {
        "pattern": _text("Regex pattern:"),
        "flags": flags,
        "text": _multi_text("Test text."),
    }


def _collect_cidr() -> dict[str, Any]:
    return {
        "cidr": _text("CIDR (example: 192.168.1.0/24):"),
        "check_ip": _text("Check IP in range (optional):"),
        "subnet_count": _int("Split into N subnets (0 to skip):", 0, minimum=0),
    }


def _collect_image_search() -> dict[str, Any]:
    engines = inquirer.checkbox(
        message="Reverse image engines (empty = all)",
        choices=[
            {"name": "Yandex", "value": "Yandex"},
            {"name": "Google Lens", "value": "Google Lens"},
            {"name": "Bing", "value": "Bing"},
            {"name": "TinEye", "value": "TinEye"},
            {"name": "SauceNao", "value": "SauceNao"},
            {"name": "IQDB", "value": "IQDB"},
            {"name": "Ascii2D", "value": "Ascii2D"},
            {"name": "TraceMoe", "value": "TraceMoe"},
            {"name": "Baidu", "value": "Baidu"},
            {"name": "Sogou", "value": "Sogou"},
        ],
    ).execute()
    return {"file_path": _text("Image file path:"), "search_engines": engines}


def collect_tool_input(tool_name: str, tool_spec: ToolSpec) -> tuple[bool, Any]:
    """Return (ok, value) for the selected tool."""
    input_type = tool_spec.input_type
    if input_type is None:
        return True, None
    try:
        if input_type == "text":
            value = _text(tool_spec.prompt or "Enter value:")
            if tool_name == "Check IP":
                return True, {"ip": value}
            if tool_name in {"HTTP Inspector", "Tech Detector", "CMS Audit"}:
                return True, {"url": value}
            if tool_name == "Subdomain finder":
                save = _confirm("Save subdomain list to file?", False)
                return True, [value, "y" if save else "n"]
            if tool_name == "Web-crawler":
                max_pages = _int("Max pages:", 20, minimum=1)
                save = _confirm("Save crawled pages to file?", False)
                return True, [value, str(max_pages), "y" if save else "n"]
            return True, value
        if input_type == "telegram":
            return True, _collect_telegram()
        if input_type == "google_osint":
            return True, _collect_google_osint()
        if input_type == "username_osint_dialog":
            return True, {"username": _text("Username or nickname:")}
        if input_type == "hash":
            return True, _collect_hash(tool_name)
        if input_type == "jwt":
            return True, _collect_jwt()
        if input_type == "web_security":
            return True, _collect_web_security()
        if input_type == "text_transformer":
            return True, _collect_text_transformer()
        if input_type == "password_gen":
            return True, _collect_password_gen()
        if input_type == "regex":
            return True, _collect_regex()
        if input_type == "cidr":
            return True, _collect_cidr()
        if input_type == "image_search":
            return True, _collect_image_search()
        return True, _text(tool_spec.prompt or "Enter input:")
    except KeyboardInterrupt:
        return False, _CANCEL
