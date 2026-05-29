"""Formatting helpers for legacy console output."""

from __future__ import annotations

import re

from rich.style import Style
from rich.text import Text

BOX_DASH = "\u2500"
ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ORPHAN_ANSI_RE = re.compile(r"(?<!\x1b)\[(?:\d{1,3})(?:;\d{1,3})*m")
URL_RE = re.compile(r"https?://[^\s<>()\"']+")
TRACEBACK_START_RE = re.compile(
    r"^(Traceback \(most recent call last\):|Future exception was never retrieved)"
)
TRACEBACK_END_RE = re.compile(
    r"^(?:[\w.]+Error|[\w.]+Exception|socket\.gaierror|asyncio\.[\w.]+):\s+.+"
)


MOJIBAKE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("\u00e2\u203a\u00a7", "\u26e7"),
    ("\u00e2\u0153\u201d", "\u2714"),
    ("\u00e2\u0153\u2013", "\u2716"),
    ("\u00e2\u2020\u2019", "->"),
    ("\u00e2\u20ac\u201d", "-"),
    ("\u00e2\u20ac\u201c", "-"),
    ("\u00e2\u20ac\u00a6", "..."),
    ("\u00e2\u201d\u20ac", BOX_DASH),
    ("\u00e2\u201d\u201a", " "),
    ("\u00e2\u201d\u0152", BOX_DASH),
    ("\u00e2\u201d\u2014", BOX_DASH),
    ("\u00c2\u00b7", "\u00b7"),
)

BOX_REPLACEMENTS = {
    "\u2554": BOX_DASH,
    "\u2557": BOX_DASH,
    "\u255a": BOX_DASH,
    "\u255d": BOX_DASH,
    "\u2550": BOX_DASH,
    "\u250c": BOX_DASH,
    "\u2510": BOX_DASH,
    "\u2514": BOX_DASH,
    "\u2518": BOX_DASH,
    "\u2502": " ",
    "\u2551": " ",
    "\u2560": BOX_DASH,
    "\u2563": BOX_DASH,
    "\u2566": BOX_DASH,
    "\u2569": BOX_DASH,
    "\u256c": BOX_DASH,
    "\u251c": BOX_DASH,
    "\u2524": BOX_DASH,
    "\u252c": BOX_DASH,
    "\u2534": BOX_DASH,
    "\u253c": BOX_DASH,
}


def normalize_output(text: str) -> str:
    """Convert old console output into compact, copyable plain text."""
    cleaned = _strip_color_codes(text)
    cleaned = _fix_mojibake(cleaned)
    cleaned = _collapse_tracebacks(cleaned)
    cleaned = "".join(BOX_REPLACEMENTS.get(char, char) for char in cleaned)
    title_line = re.compile(rf"^{BOX_DASH}*\s*\[\s*(.*?)\s*\]\s*{BOX_DASH}*$")
    plain_rule = re.compile(rf"^{BOX_DASH}{{3,}}$")

    lines: list[str] = []
    for raw_line in cleaned.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        match = title_line.fullmatch(stripped)
        if match:
            label = re.sub(r"\s+", " ", match.group(1)).strip()
            lines.append(f"{BOX_DASH * 3} {label} {BOX_DASH * 40}" if label else BOX_DASH * 44)
            continue
        if plain_rule.fullmatch(stripped):
            continue
        lines.append(_compact_line(re.sub(r"^[ \t]{1,3}(?=\S)", "", line)))

    cleaned = "\n".join(lines)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def render_output(text: str) -> Text:
    """Return a Rich Text renderable with links and useful semantic colour."""
    normalized = normalize_output(text)
    rendered = Text(normalized, overflow="fold", no_wrap=False)
    _style_urls(rendered)
    _style_status_words(rendered)
    return rendered


def _strip_color_codes(text: str) -> str:
    cleaned = ANSI_RE.sub("", text)
    cleaned = ORPHAN_ANSI_RE.sub("", cleaned)
    return cleaned.replace("\r", "\n")


def _fix_mojibake(text: str) -> str:
    for broken, replacement in MOJIBAKE_REPLACEMENTS:
        text = text.replace(broken, replacement)
    return text


def _collapse_tracebacks(text: str) -> str:
    lines = text.splitlines()
    collapsed: list[str] = []
    in_traceback = False
    last_error = ""

    for line in lines:
        stripped = line.strip()
        if TRACEBACK_START_RE.match(stripped):
            in_traceback = True
            last_error = ""
            continue

        if in_traceback:
            if TRACEBACK_END_RE.match(stripped) or stripped.startswith("Error:"):
                last_error = stripped
            continue

        collapsed.append(line)

    if in_traceback:
        collapsed.append(f"Error: {last_error or 'background task failed'}")

    return "\n".join(collapsed)


def _compact_line(line: str, max_length: int = 220) -> str:
    if len(line) <= max_length or URL_RE.fullmatch(line.strip()):
        return line
    if "http://" in line or "https://" in line:
        return line
    return f"{line[: max_length - 3]}..."


def _style_urls(text: Text) -> None:
    for match in URL_RE.finditer(text.plain):
        url = match.group(0).rstrip(".,;")
        end = match.start() + len(url)
        text.stylize(Style(color="bright_magenta", underline=True, link=url), match.start(), end)


def _style_status_words(text: Text) -> None:
    styles = {
        "Error": "bold red",
        "failed": "red",
        "Invalid": "red",
        "No ": "yellow",
        "Found": "bold green",
        "OK": "bold green",
        "complete": "green",
    }
    plain = text.plain
    for word, style in styles.items():
        start = 0
        while True:
            index = plain.find(word, start)
            if index == -1:
                break
            text.stylize(style, index, index + len(word))
            start = index + len(word)
