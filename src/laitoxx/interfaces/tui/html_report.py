"""HTML report generator for the CLI.

This module creates self–contained HTML reports from tool results.  When
graphs are included the mermaid.js library is loaded from a CDN and the
graph text is embedded directly in the page.  Reports are saved into
a ``reports`` directory in the project root.
"""

from __future__ import annotations

import os
import webbrowser
from contextlib import suppress
from datetime import datetime
from html import escape

from laitoxx.core.settings.paths import ROOT_DIR


def generate_report(title: str, tool_results: str, graph: object | None = None) -> str:
    """Build a simple HTML document containing results and an optional graph.

    Parameters
    ----------
    title: str
        Title displayed in the report header and ``<title>`` tag.
    tool_results: str
        Preformatted text containing the tool output.  This text will be
        wrapped in a ``<pre>`` tag with whitespace preserved.
    graph: object, optional
        A graph object that implements ``generate_mermaid()``; if provided
        its Mermaid definition will be embedded into the page.

    Returns
    -------
    str
        The full HTML document as a Unicode string.
    """
    mermaid_text = ""
    if graph is not None:
        try:
            mermaid_text = graph.generate_mermaid()
        except Exception:
            mermaid_text = ""
    safe_title = escape(title or "Report")
    safe_results = escape(tool_results or "")
    safe_mermaid = escape(mermaid_text)
    mermaid_section = (
        f'\n    <h2>Graph</h2>\n    <div class="mermaid">\n{safe_mermaid}\n    </div>\n'
        if mermaid_text
        else ""
    )
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta http-equiv=\"X-UA-Compatible\" content=\"IE=edge\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>{safe_title}</title>
    <script src=\"https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js\"></script>
    <script>mermaid.initialize({{ startOnLoad: true }});</script>
    <style>
        body {{
            font-family: sans-serif;
            background: #101218;
            color: #e8eaf0;
            padding: 1rem;
            line-height: 1.45;
        }}
        h1, h2 {{ color: #7dd3fc; }}
        .meta {{ font-size: 0.9rem; color: #9ca3af; margin-bottom: 1rem; }}
        pre {{
            background: #171b24;
            padding: 1rem;
            border: 1px solid #334155;
            border-radius: 8px;
            overflow-x: auto;
        }}
        .mermaid {{
            background: #171b24;
            border: 1px solid #334155;
            padding: 1rem;
            border-radius: 8px;
        }}
    </style>
</head>
<body>
    <h1>Laitoxx Report - {safe_title}</h1>
    <div class=\"meta\">Generated: {now}</div>
    <h2>Results</h2>
    <pre>{safe_results}</pre>
    {mermaid_section}
</body>
</html>
"""
    return html


def save_and_open(html: str, filename: str) -> str:
    """Save an HTML document and open it in the default web browser.

    The report is written into a ``reports`` directory at the project
    root.  If the directory does not exist it is created.  After
    saving, the absolute path is passed to ``webbrowser.open`` to
    launch the report.  Returns the absolute file path.
    """
    reports_dir = os.path.join(ROOT_DIR, "reports")
    os.makedirs(reports_dir, exist_ok=True)
    abs_path = os.path.join(reports_dir, filename)
    with open(abs_path, "w", encoding="utf-8") as f:
        f.write(html)
    # Headless environments may reject browser launches; the saved path still matters.
    with suppress(Exception):
        webbrowser.open(f"file://{abs_path}")
    return abs_path
