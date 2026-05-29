from __future__ import annotations

import json
import re
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

from laitoxx.core.settings.paths import ROOT_DIR

MAX_RECORDS = 1000
MAX_GRAPH_NODES = 550
MAX_GRAPH_LINKS = 1200
MAX_RAW_CHARS = 250_000


def is_leakosint_plugin(plugin: Any) -> bool:
    """Return True for the bundled LeakOSINT Lua plugin."""
    blob = " ".join(
        str(getattr(plugin, attr, "") or "")
        for attr in ("id", "name", "description", "filepath")
    ).casefold()
    return "leakosint" in blob or "leak osint" in blob


def create_leakosint_report(
    result_text: str | None,
    *,
    graph_paths: list[str] | tuple[str, ...] | None = None,
    query: str = "",
    output_dir: str | Path | None = None,
) -> str | None:
    """Create a self-contained responsive HTML report from LeakOSINT JSON."""
    payload = _repair_tree(_extract_json(result_text or ""))
    graph = _load_graph(graph_paths or ())
    if payload is None and graph is None:
        return None

    databases, rows = _summarize_payload(payload)
    report_graph = _graph_from_saved(graph) if graph else _graph_from_payload(payload, query)
    title_query = query or _query_from_graph(graph) or "LeakOSINT search"
    report_data = {
        "title": f"LeakOSINT Report - {title_query}",
        "query": title_query,
        "generatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "databases": databases,
        "rows": rows,
        "columns": _top_columns(rows),
        "graph": report_graph,
        "raw": (result_text or "")[:MAX_RAW_CHARS],
        "rawJson": payload,
    }

    reports_dir = Path(output_dir) if output_dir else Path(ROOT_DIR) / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now():%Y%m%d_%H%M%S}_LeakOSINT_{_safe_name(title_query)}.html"
    path = reports_dir / filename
    path.write_text(_build_html(report_data), encoding="utf-8")
    return str(path)


def _extract_json(text: str) -> Any:
    if not text.strip():
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\{\[]", text[:MAX_RAW_CHARS]):
        try:
            value, _end = decoder.raw_decode(text[match.start() :])
        except json.JSONDecodeError:
            continue
        if isinstance(value, (dict, list)):
            return value
    return None


def _repair_tree(value: Any) -> Any:
    if isinstance(value, str):
        if any(marker in value for marker in ("\u00d0", "\u00d1", "\u00c3", "\u00c2", "\u00e2")):
            for encoding in ("cp1252", "latin1"):
                try:
                    repaired = value.encode(encoding).decode("utf-8")
                except UnicodeError:
                    continue
                return repaired
        return value.replace("\ufffd", "")
    if isinstance(value, dict):
        return {str(_repair_tree(k)): _repair_tree(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_repair_tree(item) for item in value]
    return value


def _load_graph(paths: list[str] | tuple[str, ...]) -> dict[str, Any] | None:
    for raw_path in paths:
        try:
            path = Path(raw_path)
            if path.is_file():
                return _repair_tree(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _summarize_payload(payload: Any) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    databases: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    list_obj = payload.get("List") if isinstance(payload, dict) else None
    if not isinstance(list_obj, dict):
        return databases, rows

    for db_name, db_value in list_obj.items():
        if not isinstance(db_value, dict):
            continue
        records = db_value.get("Data") if isinstance(db_value.get("Data"), list) else []
        count = db_value.get("NumOfResults", len(records))
        databases.append(
            {
                "name": str(db_name),
                "count": count,
                "info": str(db_value.get("InfoLeak") or ""),
            }
        )
        for index, record in enumerate(records, 1):
            if len(rows) >= MAX_RECORDS:
                break
            if isinstance(record, dict):
                clean = {str(k): _short_value(v) for k, v in record.items() if v not in ("", None)}
                rows.append({"__db": str(db_name), "__row": index, **clean})
    return databases, rows


def _top_columns(rows: list[dict[str, Any]], limit: int = 12) -> list[str]:
    counts: dict[str, int] = {}
    for row in rows:
        for key in row:
            if not key.startswith("__"):
                counts[key] = counts.get(key, 0) + 1
    return ["__db", "__row", *[key for key, _ in sorted(counts.items(), key=lambda x: -x[1])[:limit]]]


def _graph_from_saved(graph: dict[str, Any]) -> dict[str, Any]:
    nodes = []
    for item in graph.get("nodes", [])[:MAX_GRAPH_NODES]:
        nodes.append(
            {
                "id": str(item.get("id")),
                "label": str(item.get("label") or ""),
                "type": str(item.get("node_type") or "Custom"),
                "description": str(item.get("description") or ""),
                "color": _style_value(str(item.get("mermaid_style") or ""), "fill") or "#8b5cf6",
                "stroke": _style_value(str(item.get("mermaid_style") or ""), "stroke") or "#312e81",
            }
        )
    node_ids = {node["id"] for node in nodes}
    links = [
        {
            "source": str(edge.get("source_id")),
            "target": str(edge.get("target_id")),
            "label": str(edge.get("label") or ""),
            "color": _style_value(str(edge.get("mermaid_style") or ""), "stroke") or "#94a3b8",
        }
        for edge in graph.get("edges", [])
        if str(edge.get("source_id")) in node_ids and str(edge.get("target_id")) in node_ids
    ][:MAX_GRAPH_LINKS]
    return {"nodes": nodes, "links": links}


def _graph_from_payload(payload: Any, query: str) -> dict[str, Any]:
    nodes = [{"id": "query", "label": query or "Query", "type": "Query", "color": "#facc15"}]
    links = []
    list_obj = payload.get("List") if isinstance(payload, dict) else {}
    if not isinstance(list_obj, dict):
        return {"nodes": nodes, "links": links}

    for db_index, (db_name, db_value) in enumerate(list_obj.items()):
        if len(nodes) >= MAX_GRAPH_NODES:
            break
        db_id = f"db-{db_index}"
        nodes.append({"id": db_id, "label": str(db_name), "type": "Database", "color": "#38bdf8"})
        links.append({"source": "query", "target": db_id, "label": "database", "color": "#38bdf8"})
        records = db_value.get("Data") if isinstance(db_value, dict) else []
        for row_index, record in enumerate(records[:15] if isinstance(records, list) else []):
            if len(nodes) >= MAX_GRAPH_NODES or not isinstance(record, dict):
                break
            record_id = f"{db_id}-r-{row_index}"
            nodes.append({"id": record_id, "label": _record_label(record, row_index), "type": "Record", "color": "#a78bfa"})
            links.append({"source": db_id, "target": record_id, "label": "record", "color": "#94a3b8"})
            for key, value in list(record.items())[:8]:
                if len(nodes) >= MAX_GRAPH_NODES or value in ("", None):
                    break
                node_id = f"{record_id}-{len(nodes)}"
                nodes.append({"id": node_id, "label": _short_value(value, 48), "type": _infer_type(key, value), "color": _type_color(key, value)})
                links.append({"source": record_id, "target": node_id, "label": str(key), "color": "#64748b"})
    return {"nodes": nodes, "links": links[:MAX_GRAPH_LINKS]}


def _build_html(report_data: dict[str, Any]) -> str:  # noqa: PLR0915
    data = json.dumps(report_data, ensure_ascii=False).replace("</", "<\\/")
    title_safe = escape(str(report_data["title"]))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_safe}</title>
<style>
/* ── tokens ─────────────────────────────────────────────────────────── */
:root {{
  --bg:      #080d18;
  --surface: #0e1525;
  --card:    #111c2e;
  --glass:   rgba(14,21,37,.72);
  --border:  rgba(56,189,248,.13);
  --border2: rgba(56,189,248,.22);
  --text:    #e2e8f0;
  --muted:   #7b90a8;
  --dim:     #3e526a;
  --accent:  #38bdf8;
  --accent2: #818cf8;
  --green:   #34d399;
  --amber:   #fbbf24;
  --rose:    #fb7185;
  --purple:  #a78bfa;
  --radius:  12px;
  --shadow:  0 8px 32px rgba(0,0,0,.45);
}}
body.theme-light {{
  --bg:#f0f4f8; --surface:#fff; --card:#f8fafc; --glass:rgba(255,255,255,.82);
  --border:rgba(0,0,0,.09); --border2:rgba(0,0,0,.15);
  --text:#0f172a; --muted:#64748b; --dim:#94a3b8;
  --shadow:0 8px 32px rgba(0,0,0,.12);
}}
body.theme-contrast {{
  --bg:#000; --surface:#0a0a0a; --card:#111; --glass:rgba(0,0,0,.9);
  --border:rgba(255,255,0,.3); --accent:#ff0; --text:#fff; --muted:#aaa;
}}

/* ── reset + base ────────────────────────────────────────────────────── */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0 }}
html {{ scroll-behavior: smooth }}
body {{
  background: var(--bg);
  color: var(--text);
  font: 14px/1.6 "Inter", "Segoe UI", system-ui, sans-serif;
  min-height: 100vh;
  background-image:
    radial-gradient(ellipse 80% 60% at 20% -10%, rgba(56,189,248,.07) 0%, transparent 60%),
    radial-gradient(ellipse 60% 50% at 80% 110%, rgba(129,140,248,.06) 0%, transparent 60%);
}}

/* ── scrollbar ───────────────────────────────────────────────────────── */
::-webkit-scrollbar {{ width:6px; height:6px }}
::-webkit-scrollbar-track {{ background: var(--surface) }}
::-webkit-scrollbar-thumb {{ background: var(--dim); border-radius:99px }}
::-webkit-scrollbar-thumb:hover {{ background: var(--accent) }}

/* ── header ──────────────────────────────────────────────────────────── */
header {{
  position: sticky; top: 0; z-index: 100;
  display: flex; align-items: center; justify-content: space-between; gap: 16px;
  padding: 14px 24px;
  background: var(--glass);
  backdrop-filter: blur(20px) saturate(180%);
  border-bottom: 1px solid var(--border);
  box-shadow: 0 1px 0 var(--border2), var(--shadow);
}}
.header-left {{ min-width: 0 }}
.report-title {{
  font-size: clamp(16px,2.5vw,26px); font-weight: 700; letter-spacing:-.3px;
  color: var(--text); cursor: text; outline: none;
  border-radius: 6px; padding: 2px 6px; margin: -2px -6px;
  transition: background .15s;
}}
.report-title:hover {{ background: rgba(56,189,248,.06) }}
.report-title:focus {{ background: rgba(56,189,248,.11); outline: 2px solid var(--accent) }}
.report-meta {{ font-size:12px; color: var(--muted); margin-top:3px }}
.header-actions {{ display:flex; gap:8px; flex-shrink:0 }}

/* ── buttons ─────────────────────────────────────────────────────────── */
.btn {{
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 14px; border-radius: 8px; font-size: 13px; font-weight: 500;
  cursor: pointer; border: 1px solid var(--border2); transition: all .15s;
  background: var(--card); color: var(--text);
}}
.btn:hover {{ border-color: var(--accent); color: var(--accent); background: rgba(56,189,248,.07) }}
.btn-accent {{ background: var(--accent); color: #020617; border-color: var(--accent) }}
.btn-accent:hover {{ background: #7dd3fc; border-color: #7dd3fc; color: #020617 }}
.btn svg {{ flex-shrink:0 }}

/* ── layout ──────────────────────────────────────────────────────────── */
.layout {{
  display: grid;
  grid-template-columns: 280px minmax(0,1fr);
  gap: 0;
  min-height: calc(100vh - 60px);
}}
.sidebar {{
  background: var(--surface);
  border-right: 1px solid var(--border);
  padding: 20px 16px;
  position: sticky; top: 60px;
  height: calc(100vh - 60px);
  overflow-y: auto;
  display: flex; flex-direction: column; gap: 24px;
}}
.content {{ padding: 20px 24px; display: flex; flex-direction: column; gap: 20px }}

/* ── sidebar sections ────────────────────────────────────────────────── */
.sidebar-section h3 {{
  font-size: 10px; font-weight: 700; letter-spacing: 1.2px;
  text-transform: uppercase; color: var(--dim);
  margin-bottom: 10px; padding-bottom: 6px;
  border-bottom: 1px solid var(--border);
}}
.form-row {{ display: grid; gap: 6px; margin-bottom: 10px }}
.form-label {{ font-size: 12px; color: var(--muted); font-weight: 500 }}
.form-input, .form-select {{
  width: 100%; padding: 7px 10px;
  background: var(--card); border: 1px solid var(--border2);
  border-radius: 8px; color: var(--text); font-size: 13px;
  transition: border-color .15s;
}}
.form-input:focus, .form-select:focus {{
  outline: none; border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(56,189,248,.12);
}}
.form-range {{ width:100%; accent-color: var(--accent) }}
.form-check {{ display:flex; align-items:center; gap:8px; font-size:13px; cursor:pointer }}
.form-check input {{ accent-color:var(--accent); width:15px; height:15px }}

.db-item {{
  padding: 10px 12px; border-radius: 10px;
  background: var(--card); border: 1px solid var(--border);
  margin-bottom: 8px; transition: border-color .15s;
}}
.db-item:hover {{ border-color: var(--border2) }}
.db-item-name {{
  font-size: 13px; font-weight: 600; color: var(--accent);
  display: flex; align-items: center; gap: 6px; margin-bottom: 4px;
}}
.db-item-count {{ font-size: 20px; font-weight: 700; color: var(--text) }}
.db-item-label {{ font-size: 11px; color: var(--muted) }}
.db-item-info {{ font-size: 11px; color: var(--muted); margin-top: 4px; line-height:1.4 }}

.notes-area {{
  width: 100%; min-height: 80px; padding: 10px;
  background: var(--card); border: 1px dashed var(--border2);
  border-radius: 8px; color: var(--text); font-size: 13px;
  font-family: inherit; resize: vertical;
}}
.notes-area:focus {{ outline: none; border-color: var(--accent) }}

/* ── stat cards ──────────────────────────────────────────────────────── */
.stats-grid {{
  display: grid; grid-template-columns: repeat(4, minmax(0,1fr)); gap: 14px;
}}
.stat-card {{
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px 18px;
  position: relative; overflow: hidden;
  transition: border-color .2s, transform .15s;
}}
.stat-card:hover {{ border-color: var(--border2); transform: translateY(-1px) }}
.stat-card::before {{
  content: ''; position: absolute; inset: 0; opacity: .06;
  background: var(--card-glow, var(--accent));
  border-radius: inherit;
}}
.stat-card-icon {{ font-size: 20px; margin-bottom: 8px }}
.stat-card-value {{
  font-size: 28px; font-weight: 800; letter-spacing: -1px;
  color: var(--card-color, var(--accent)); line-height: 1;
}}
.stat-card-label {{ font-size: 12px; color: var(--muted); margin-top: 4px }}

/* ── panel ───────────────────────────────────────────────────────────── */
.panel {{
  background: var(--card); border: 1px solid var(--border);
  border-radius: var(--radius); overflow: hidden;
  box-shadow: var(--shadow);
}}
.panel-head {{
  display: flex; align-items: center; justify-content: space-between;
  padding: 14px 18px; border-bottom: 1px solid var(--border);
  background: rgba(56,189,248,.03);
}}
.panel-title {{
  font-size: 14px; font-weight: 600; color: var(--text);
  display: flex; align-items: center; gap: 8px;
}}
.panel-title svg {{ color: var(--accent) }}
.panel-body {{ padding: 16px 18px }}

/* ── tabs ────────────────────────────────────────────────────────────── */
.tabs {{ display:flex; gap:4px; padding: 14px 18px 0; border-bottom: 1px solid var(--border) }}
.tab {{
  padding: 7px 14px; font-size: 13px; font-weight: 500;
  border-radius: 8px 8px 0 0; cursor: pointer;
  color: var(--muted); border: 1px solid transparent;
  border-bottom: none; transition: all .15s; background: none;
  position: relative; bottom: -1px;
}}
.tab:hover {{ color: var(--text) }}
.tab.active {{
  color: var(--accent); border-color: var(--border); border-bottom-color: var(--card);
  background: var(--card);
}}
.tab-panel {{ display:none; padding:16px 18px }}
.tab-panel.active {{ display:block }}

/* ── graph canvas ────────────────────────────────────────────────────── */
.graph-wrap {{
  position: relative; background: #050a14;
  border-radius: 0 0 var(--radius) var(--radius);
}}
#graphCanvas {{
  width: 100%; height: 540px; display: block;
  cursor: grab; border-radius: 0 0 var(--radius) var(--radius);
}}
#graphCanvas:active {{ cursor: grabbing }}
.graph-controls {{
  position: absolute; top: 12px; right: 12px;
  display: flex; gap: 6px;
}}
.graph-btn {{
  width: 32px; height: 32px; border-radius: 8px; border: 1px solid var(--border2);
  background: rgba(8,13,24,.8); backdrop-filter: blur(8px);
  color: var(--muted); cursor: pointer; font-size: 14px;
  display: flex; align-items: center; justify-content: center;
  transition: all .15s;
}}
.graph-btn:hover {{ border-color: var(--accent); color: var(--accent) }}
.graph-legend {{
  position: absolute; bottom: 12px; left: 12px;
  background: rgba(8,13,24,.8); backdrop-filter: blur(8px);
  border: 1px solid var(--border); border-radius: 8px;
  padding: 8px 12px; font-size: 11px; color: var(--muted);
  display: flex; gap: 10px; flex-wrap: wrap;
}}
.legend-dot {{
  display: inline-block; width: 8px; height: 8px;
  border-radius: 50%; margin-right: 4px; vertical-align: middle;
}}
.graph-tooltip {{
  position: absolute; pointer-events: none;
  background: rgba(8,13,24,.95); border: 1px solid var(--border2);
  border-radius: 8px; padding: 8px 12px; font-size: 12px;
  color: var(--text); max-width: 220px; display: none;
  box-shadow: var(--shadow);
}}

/* ── table ───────────────────────────────────────────────────────────── */
.table-wrap {{ overflow: auto; max-height: 520px }}
table {{ width: 100%; border-collapse: collapse; min-width: 720px }}
thead th {{
  position: sticky; top: 0; z-index: 2;
  padding: 10px 12px; text-align: left; font-size: 12px;
  font-weight: 600; letter-spacing: .4px; text-transform: uppercase;
  color: var(--accent); background: var(--surface);
  border-bottom: 2px solid var(--border2); white-space: nowrap;
  cursor: pointer; user-select: none;
}}
thead th:hover {{ color: var(--text) }}
thead th.sorted-asc::after {{ content: " ↑" }}
thead th.sorted-desc::after {{ content: " ↓" }}
tbody tr {{ border-bottom: 1px solid var(--border); transition: background .1s }}
tbody tr:hover {{ background: rgba(56,189,248,.04) }}
tbody tr:nth-child(even) {{ background: rgba(255,255,255,.015) }}
tbody tr:hover {{ background: rgba(56,189,248,.06) }}
td {{
  padding: 9px 12px; font-size: 13px; vertical-align: top;
  max-width: 260px; word-break: break-word;
}}
td[contenteditable=true]:focus {{
  outline: 2px solid var(--accent); border-radius: 4px;
  background: rgba(56,189,248,.07);
}}
.td-db {{
  font-size: 11px; font-weight: 600; color: var(--accent);
  white-space: nowrap;
}}
.td-row {{ color: var(--dim); font-size: 11px }}
.td-email {{ color: #38bdf8 }}
.td-phone {{ color: #34d399 }}
.td-ip    {{ color: #fb7185 }}
.td-addr  {{ color: #fbbf24 }}
.td-person{{ color: #a78bfa }}

/* ── raw json ────────────────────────────────────────────────────────── */
.raw-pre {{
  white-space: pre-wrap; word-break: break-word;
  max-height: 420px; overflow: auto;
  background: #050a14; border: 1px solid var(--border);
  border-radius: 8px; padding: 14px 16px;
  font-family: "Fira Code","Cascadia Code","Consolas",monospace;
  font-size: 12.5px; line-height: 1.7; color: #94a3b8;
}}

/* ── pill badge ──────────────────────────────────────────────────────── */
.pill {{
  display: inline-flex; align-items: center; gap: 5px;
  padding: 3px 9px; border-radius: 99px; font-size: 11px; font-weight: 600;
  border: 1px solid currentColor; opacity: .85;
}}

/* ── search highlight ────────────────────────────────────────────────── */
mark {{ background: rgba(251,191,36,.35); color: inherit; border-radius: 2px }}

/* ── progress bar ────────────────────────────────────────────────────── */
.db-bar-wrap {{ height: 4px; background: var(--border); border-radius: 99px; margin-top: 6px }}
.db-bar {{ height: 4px; border-radius: 99px; background: var(--accent); transition: width .4s }}

/* ── loading spinner ─────────────────────────────────────────────────── */
@keyframes spin {{ to{{ transform:rotate(360deg) }} }}
.spinner {{
  width: 32px; height: 32px; border: 3px solid var(--border);
  border-top-color: var(--accent); border-radius: 50%;
  animation: spin .7s linear infinite; margin: 40px auto;
}}

/* ── animations ──────────────────────────────────────────────────────── */
@keyframes fadeIn {{ from{{ opacity:0;transform:translateY(8px) }} to{{ opacity:1;transform:none }} }}
.panel, .stat-card {{ animation: fadeIn .3s ease both }}
.stat-card:nth-child(2) {{ animation-delay:.05s }}
.stat-card:nth-child(3) {{ animation-delay:.1s }}
.stat-card:nth-child(4) {{ animation-delay:.15s }}

/* ── responsive ──────────────────────────────────────────────────────── */
@media (max-width: 1024px) {{
  .layout {{ grid-template-columns: 1fr }}
  .sidebar {{ position:static; height:auto; flex-direction:row; flex-wrap:wrap }}
  .sidebar-section {{ flex: 1 1 200px }}
  .stats-grid {{ grid-template-columns: repeat(2,1fr) }}
}}
@media (max-width: 640px) {{
  .header-actions {{ display:none }}
  .stats-grid {{ grid-template-columns: repeat(2,1fr) }}
  .content {{ padding: 12px }}
  #graphCanvas {{ height: 400px }}
}}
@media print {{
  .sidebar, header .btn, .graph-controls {{ display:none }}
  .layout {{ grid-template-columns: 1fr }}
  .panel {{ break-inside: avoid; box-shadow:none; border:1px solid #ccc }}
  body {{ background:#fff; color:#000 }}
}}
</style>
</head>
<body>

<header>
  <div class="header-left">
    <h1 class="report-title" id="reportTitle" contenteditable="true"></h1>
    <div class="report-meta" id="reportMeta"></div>
  </div>
  <div class="header-actions">
    <button class="btn" id="copyBtn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
      Copy link
    </button>
    <button class="btn" id="jsonBtn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
      Export JSON
    </button>
    <button class="btn btn-accent" id="printBtn">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
      Print
    </button>
  </div>
</header>

<div class="layout">

<!-- ── Sidebar ─────────────────────────────────────────────────────── -->
<aside class="sidebar">

  <div class="sidebar-section">
    <h3>Search &amp; Filter</h3>
    <div class="form-row">
      <label class="form-label">Search records &amp; graph</label>
      <input class="form-input" id="filterInput" type="search" placeholder="email, phone, name…" autocomplete="off">
    </div>
  </div>

  <div class="sidebar-section">
    <h3>Appearance</h3>
    <div class="form-row">
      <label class="form-label">Theme</label>
      <select class="form-select" id="themeSelect">
        <option value="">Dark (default)</option>
        <option value="theme-light">Light</option>
        <option value="theme-contrast">High contrast</option>
      </select>
    </div>
    <div class="form-row">
      <label class="form-label">Accent colour</label>
      <input class="form-input" id="accentColor" type="color" value="#38bdf8" style="height:36px;padding:2px 6px">
    </div>
  </div>

  <div class="sidebar-section">
    <h3>Graph</h3>
    <div class="form-row">
      <label class="form-label">Node size <span id="nodeSizeVal">14</span>px</label>
      <input class="form-range" id="nodeSize" type="range" min="6" max="28" value="14">
    </div>
    <div class="form-row">
      <label class="form-label">Repulsion <span id="forceVal">54</span></label>
      <input class="form-range" id="forceRange" type="range" min="10" max="140" value="54">
    </div>
    <div class="form-row">
      <label class="form-label">Link distance <span id="linkDistVal">120</span>px</label>
      <input class="form-range" id="linkDist" type="range" min="40" max="280" value="120">
    </div>
    <label class="form-check">
      <input type="checkbox" id="showLabels" checked> Show node labels
    </label>
    <label class="form-check" style="margin-top:8px">
      <input type="checkbox" id="showArrows" checked> Show arrows
    </label>
  </div>

  <div class="sidebar-section" style="flex:1">
    <h3>Databases</h3>
    <div id="dbList"></div>
  </div>

  <div class="sidebar-section">
    <h3>Analyst notes</h3>
    <textarea class="notes-area" id="notes" placeholder="Add your notes here…"></textarea>
  </div>

</aside>

<!-- ── Main content ─────────────────────────────────────────────────── -->
<main class="content">

  <!-- Stats -->
  <div class="stats-grid" id="statsGrid"></div>

  <!-- Graph panel -->
  <div class="panel">
    <div class="panel-head">
      <span class="panel-title">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
        Relationship Graph
      </span>
      <div style="display:flex;gap:6px;align-items:center">
        <span id="graphNodeCount" style="font-size:12px;color:var(--muted)"></span>
      </div>
    </div>
    <div class="graph-wrap">
      <canvas id="graphCanvas"></canvas>
      <div class="graph-controls">
        <button class="graph-btn" id="zoomIn" title="Zoom in">+</button>
        <button class="graph-btn" id="zoomOut" title="Zoom out">−</button>
        <button class="graph-btn" id="resetView" title="Reset view">⊙</button>
        <button class="graph-btn" id="pauseBtn" title="Pause physics">⏸</button>
      </div>
      <div class="graph-legend" id="graphLegend"></div>
      <div class="graph-tooltip" id="graphTooltip"></div>
    </div>
    <div style="padding:10px 18px;border-top:1px solid var(--border);font-size:12px;color:var(--muted)">
      Drag nodes · Scroll to zoom · Click to inspect · Use controls to reset view
    </div>
  </div>

  <!-- Records panel with tabs -->
  <div class="panel">
    <div class="tabs" id="mainTabs">
      <button class="tab active" data-tab="records">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline;vertical-align:middle;margin-right:4px"><rect x="3" y="3" width="18" height="18" rx="2"/><line x1="3" y1="9" x2="21" y2="9"/><line x1="3" y1="15" x2="21" y2="15"/><line x1="9" y1="3" x2="9" y2="21"/></svg>
        Records <span id="recordCountBadge" style="background:var(--accent);color:#020617;border-radius:99px;padding:1px 7px;font-size:11px;margin-left:4px"></span>
      </button>
      <button class="tab" data-tab="raw">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="display:inline;vertical-align:middle;margin-right:4px"><polyline points="16 18 22 12 16 6"/><polyline points="8 6 2 12 8 18"/></svg>
        Raw JSON
      </button>
    </div>
    <div class="tab-panel active" id="tab-records">
      <div class="table-wrap">
        <table id="recordsTable"></table>
      </div>
    </div>
    <div class="tab-panel" id="tab-raw">
      <pre class="raw-pre" id="rawPre"></pre>
    </div>
  </div>

</main>
</div>

<script id="report-data" type="application/json">{data}</script>
<script>
(function(){{
'use strict';
const R=JSON.parse(document.getElementById('report-data').textContent);
const $=id=>document.getElementById(id);

/* ── helpers ─────────────────────────────────────────────────────────── */
function esc(v){{
  return String(v??'').replace(/[&<>"']/g,m=>
    ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m]));
}}
function colClass(key,val){{
  const t=`${{key}} ${{val}}`.toLowerCase();
  if(/@/.test(val)) return 'td-email';
  if(/phone|mobile/.test(t)||/^[\\d\\s+().\\-]{{7,}}$/.test(String(val))) return 'td-phone';
  if(/\\b\\d{{1,3}}\\.\\d{{1,3}}\\.\\d{{1,3}}\\.\\d{{1,3}}\\b/.test(String(val))) return 'td-ip';
  if(/address|city|street|region|zip/.test(t)) return 'td-addr';
  if(/name|fio|surname/.test(t)) return 'td-person';
  return '';
}}

/* ── init ─────────────────────────────────────────────────────────────── */
$('reportTitle').textContent=R.title;
$('reportMeta').textContent=`Query: ${{R.query}} · Generated: ${{R.generatedAt}}`;

/* ── stats ────────────────────────────────────────────────────────────── */
(function renderStats(){{
  const fields=new Set(R.rows.flatMap(r=>Object.keys(r).filter(k=>!k.startsWith('__'))));
  const defs=[
    {{icon:'🗄️', label:'Databases', val:R.databases.length, color:'var(--accent)'}},
    {{icon:'📄', label:'Records',   val:R.rows.length,       color:'var(--green)'}},
    {{icon:'🔑', label:'Fields',    val:fields.size,          color:'var(--amber)'}},
    {{icon:'🔵', label:'Graph nodes',val:R.graph.nodes.length,color:'var(--purple)'}},
  ];
  $('statsGrid').innerHTML=defs.map((d,i)=>
    `<div class="stat-card" style="--card-color:${{d.color}};--card-glow:${{d.color}};animation-delay:${{i*.06}}s">
      <div class="stat-card-icon">${{d.icon}}</div>
      <div class="stat-card-value" style="color:${{d.color}}">${{d.val.toLocaleString()}}</div>
      <div class="stat-card-label">${{d.label}}</div>
    </div>`
  ).join('');
}})();

/* ── databases sidebar ────────────────────────────────────────────────── */
(function renderDbList(){{
  const max=Math.max(1,...R.databases.map(d=>Number(d.count)||0));
  $('dbList').innerHTML=R.databases.map(d=>{{
    const pct=Math.round((Number(d.count)||0)/max*100);
    const colors=['#38bdf8','#34d399','#a78bfa','#fbbf24','#fb7185','#f97316'];
    const c=colors[R.databases.indexOf(d)%colors.length];
    return `<div class="db-item">
      <div class="db-item-name" style="color:${{c}}">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5"/><path d="M3 12c0 1.66 4.03 3 9 3s9-1.34 9-3"/></svg>
        ${{esc(d.name)}}
      </div>
      <div class="db-item-count">${{Number(d.count).toLocaleString()}}</div>
      <div class="db-item-label">records</div>
      ${{d.info?`<div class="db-item-info">${{esc(d.info)}}</div>`:''}}
      <div class="db-bar-wrap"><div class="db-bar" style="width:${{pct}}%;background:${{c}}"></div></div>
    </div>`;
  }}).join('')||'<p style="color:var(--muted);font-size:13px">No databases found.</p>';
}})();

/* ── table ────────────────────────────────────────────────────────────── */
let sortCol='', sortDir=1;
function filteredRows(){{
  const q=$('filterInput').value.toLowerCase().trim();
  return q?R.rows.filter(r=>JSON.stringify(r).toLowerCase().includes(q)):R.rows;
}}
function sortedRows(rows){{
  if(!sortCol) return rows;
  return [...rows].sort((a,b)=>{{
    const av=String(a[sortCol]??''), bv=String(b[sortCol]??'');
    return av.localeCompare(bv,undefined,{{numeric:true}})*sortDir;
  }});
}}
function highlightVal(v){{
  const q=$('filterInput').value.trim();
  if(!q) return esc(v);
  const s=String(v??'');
  const idx=s.toLowerCase().indexOf(q.toLowerCase());
  if(idx<0) return esc(s);
  return esc(s.slice(0,idx))+'<mark>'+esc(s.slice(idx,idx+q.length))+'</mark>'+esc(s.slice(idx+q.length));
}}
function renderTable(){{
  const cols=R.columns, rows=sortedRows(filteredRows());
  $('recordCountBadge').textContent=rows.length;
  const head=cols.map(c=>{{
    const isActive=c===sortCol;
    return `<th class="${{isActive?(sortDir>0?'sorted-asc':'sorted-desc'):''}}" data-col="${{esc(c)}}">${{esc(c.replace(/^__/,''))}}</th>`;
  }}).join('');
  const body=rows.map(r=>{{
    const cells=cols.map(c=>{{
      const v=r[c]??'';
      if(c==='__db') return `<td class="td-db">${{esc(String(v))}}</td>`;
      if(c==='__row') return `<td class="td-row">#${{esc(String(v))}}</td>`;
      return `<td contenteditable="true" class="${{colClass(c,v)}}">${{highlightVal(v)}}</td>`;
    }}).join('');
    return `<tr>${{cells}}</tr>`;
  }}).join('');
  $('recordsTable').innerHTML=`<thead><tr>${{head}}</tr></thead><tbody>${{body}}</tbody>`;
  $('recordsTable').querySelectorAll('thead th').forEach(th=>{{
    th.onclick=()=>{{
      const c=th.dataset.col;
      if(sortCol===c) sortDir*=-1; else {{ sortCol=c; sortDir=1; }}
      renderTable();
    }};
  }});
}}
renderTable();

/* ── raw JSON ─────────────────────────────────────────────────────────── */
$('rawPre').textContent=JSON.stringify(R.rawJson??R.raw??{{}},null,2);

/* ── tabs ─────────────────────────────────────────────────────────────── */
document.querySelectorAll('.tab').forEach(btn=>{{
  btn.onclick=()=>{{
    document.querySelectorAll('.tab,.tab-panel').forEach(el=>el.classList.remove('active'));
    btn.classList.add('active');
    $('tab-'+btn.dataset.tab).classList.add('active');
  }};
}});

/* ── graph ────────────────────────────────────────────────────────────── */
(function initGraph(){{
  const canvas=$('graphCanvas'), ctx=canvas.getContext('2d');
  const tooltip=$('graphTooltip');
  const W=()=>canvas.clientWidth, H=()=>canvas.clientHeight;
  let paused=false, scale=1, ox=0, oy=0, dragging=null, panning=false, panStart={{x:0,y:0}};

  const TYPE_COLORS={{
    Query:'#fbbf24', Database:'#38bdf8', Record:'#818cf8',
    Email:'#38bdf8', Phone:'#34d399', IP:'#fb7185',
    Address:'#fbbf24', Person:'#a78bfa', Custom:'#64748b',
  }};
  const nodes=R.graph.nodes.map((n,i)=>{{
    const angle=(i/Math.max(1,R.graph.nodes.length))*Math.PI*2;
    const rad=Math.min(W(),H())/3;
    return {{...n, x:W()/2+rad*Math.cos(angle), y:H()/2+rad*Math.sin(angle), vx:0, vy:0}};
  }});
  const links=R.graph.links;

  $('graphNodeCount').textContent=`${{nodes.length}} nodes · ${{links.length}} links`;

  // Legend
  const seenTypes=[...new Set(nodes.map(n=>n.type))].slice(0,8);
  $('graphLegend').innerHTML=seenTypes.map(t=>
    `<span><span class="legend-dot" style="background:${{TYPE_COLORS[t]||'#64748b'}}"></span>${{t}}</span>`
  ).join('');

  function dpr(){{ return window.devicePixelRatio||1 }}
  function resize(){{
    const d=dpr(), r=canvas.getBoundingClientRect();
    canvas.width=r.width*d; canvas.height=r.height*d;
    ctx.setTransform(d,0,0,d,0,0);
  }}
  addEventListener('resize',resize); resize();

  function visible(n){{
    const q=$('filterInput').value.toLowerCase().trim();
    return !q||`${{n.label}} ${{n.type}} ${{n.description}}`.toLowerCase().includes(q);
  }}

  // force-directed tick
  function tick(){{
    if(paused){{ draw(); requestAnimationFrame(tick); return; }}
    const force=+$('forceRange').value/1000;
    const dist0=+$('linkDist').value;

    // link spring
    for(const l of links){{
      const a=nodes.find(n=>n.id===l.source), b=nodes.find(n=>n.id===l.target);
      if(!a||!b) continue;
      const dx=b.x-a.x, dy=b.y-a.y, d=Math.max(1,Math.hypot(dx,dy));
      const pull=(d-dist0)*force;
      a.vx+=dx/d*pull; b.vx-=dx/d*pull;
      a.vy+=dy/d*pull; b.vy-=dy/d*pull;
    }}
    // repulsion
    for(let i=0;i<nodes.length;i++) for(let j=i+1;j<nodes.length;j++){{
      const a=nodes[i], b=nodes[j];
      const dx=b.x-a.x, dy=b.y-a.y, d=Math.max(5,Math.hypot(dx,dy));
      const f=60/d;
      a.vx-=dx/d*f; b.vx+=dx/d*f;
      a.vy-=dy/d*f; b.vy+=dy/d*f;
    }}
    // center gravity + damping
    for(const n of nodes){{
      n.vx+=(W()/2-n.x)*.0006; n.vy+=(H()/2-n.y)*.0006;
      n.vx*=.86; n.vy*=.86;
      if(n!==dragging){{
        n.x=Math.max(20,Math.min(W()-20,n.x+n.vx));
        n.y=Math.max(20,Math.min(H()-20,n.y+n.vy));
      }}
    }}
    draw();
    requestAnimationFrame(tick);
  }}

  function draw(){{
    const w=W(), h=H();
    ctx.save();
    ctx.clearRect(0,0,w,h);
    ctx.translate(ox,oy); ctx.scale(scale,scale);

    const showArrows=$('showArrows').checked;
    // draw links
    for(const l of links){{
      const a=nodes.find(n=>n.id===l.source), b=nodes.find(n=>n.id===l.target);
      if(!a||!b||!visible(a)||!visible(b)) continue;
      ctx.save();
      ctx.globalAlpha=.4; ctx.lineWidth=1.3;
      ctx.strokeStyle=l.color||'#64748b';
      ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
      if(l.label){{
        ctx.globalAlpha=.55; ctx.fillStyle='#94a3b8'; ctx.font='10px Segoe UI,sans-serif';
        ctx.fillText(l.label,(a.x+b.x)/2,(a.y+b.y)/2);
      }}
      if(showArrows){{
        const angle=Math.atan2(b.y-a.y,b.x-a.x);
        const r=+$('nodeSize').value+4, ax=b.x-Math.cos(angle)*r, ay=b.y-Math.sin(angle)*r;
        ctx.globalAlpha=.6; ctx.fillStyle=l.color||'#64748b';
        ctx.beginPath();
        ctx.moveTo(ax,ay);
        ctx.lineTo(ax-8*Math.cos(angle-0.4),ay-8*Math.sin(angle-0.4));
        ctx.lineTo(ax-8*Math.cos(angle+0.4),ay-8*Math.sin(angle+0.4));
        ctx.closePath(); ctx.fill();
      }}
      ctx.restore();
    }}

    // draw nodes
    const nr=+$('nodeSize').value;
    for(const n of nodes){{
      if(!visible(n)) continue;
      const c=n.color||TYPE_COLORS[n.type]||'#64748b';
      // glow
      ctx.save();
      ctx.globalAlpha=.18;
      const grd=ctx.createRadialGradient(n.x,n.y,nr*.2,n.x,n.y,nr*2.2);
      grd.addColorStop(0,c); grd.addColorStop(1,'transparent');
      ctx.fillStyle=grd; ctx.beginPath(); ctx.arc(n.x,n.y,nr*2.2,0,Math.PI*2); ctx.fill();
      ctx.restore();
      // circle
      ctx.beginPath(); ctx.arc(n.x,n.y,nr,0,Math.PI*2);
      ctx.fillStyle=c; ctx.fill();
      ctx.strokeStyle='#020617'; ctx.lineWidth=2; ctx.stroke();
      // label
      if($('showLabels').checked){{
        ctx.fillStyle='#e2e8f0'; ctx.font=`${{Math.max(10,nr-2)}}px Segoe UI,sans-serif`;
        ctx.fillText(String(n.label).slice(0,32),n.x+nr+4,n.y+4);
      }}
    }}
    ctx.restore();
  }}

  // pointer interactions
  function ptToGraph(e){{
    const r=canvas.getBoundingClientRect();
    return {{ x:(e.clientX-r.left-ox)/scale, y:(e.clientY-r.top-oy)/scale }};
  }}
  canvas.onpointerdown=e=>{{
    const p=ptToGraph(e), nr=+$('nodeSize').value+6;
    dragging=nodes.find(n=>Math.hypot(n.x-p.x,n.y-p.y)<nr)||null;
    if(!dragging){{ panning=true; panStart={{x:e.clientX-ox,y:e.clientY-oy}}; }}
  }};
  canvas.onpointermove=e=>{{
    const p=ptToGraph(e);
    if(dragging){{ dragging.x=p.x; dragging.y=p.y; dragging.vx=dragging.vy=0; return; }}
    if(panning){{ ox=e.clientX-panStart.x; oy=e.clientY-panStart.y; return; }}
    // tooltip
    const nr=+$('nodeSize').value+6;
    const hovered=nodes.find(n=>visible(n)&&Math.hypot(n.x-p.x,n.y-p.y)<nr);
    if(hovered){{
      tooltip.style.display='block';
      tooltip.style.left=(e.offsetX+18)+'px'; tooltip.style.top=(e.offsetY+8)+'px';
      tooltip.innerHTML=`<b style="color:var(--accent)">${{esc(hovered.label)}}</b><br>
        <span style="color:var(--muted);font-size:11px">${{esc(hovered.type)}}</span>
        ${{hovered.description?`<br><span style="font-size:11px">${{esc(hovered.description)}}</span>`:''}}`;
    }} else tooltip.style.display='none';
  }};
  canvas.onpointerup=canvas.onpointerleave=()=>{{ dragging=null; panning=false; }};
  canvas.onwheel=e=>{{
    e.preventDefault();
    const delta=e.deltaY>0?.9:1.1;
    const r=canvas.getBoundingClientRect();
    const mx=e.clientX-r.left, my=e.clientY-r.top;
    ox=(ox-mx)*delta+mx; oy=(oy-my)*delta+my;
    scale=Math.max(.1,Math.min(8,scale*delta));
  }};

  // graph controls
  $('zoomIn').onclick=()=>{{ scale=Math.min(8,scale*1.2) }};
  $('zoomOut').onclick=()=>{{ scale=Math.max(.1,scale*.83) }};
  $('resetView').onclick=()=>{{ scale=1; ox=0; oy=0 }};
  $('pauseBtn').onclick=()=>{{ paused=!paused; $('pauseBtn').textContent=paused?'▶':'⏸' }};

  tick();
}})();

/* ── filter ────────────────────────────────────────────────────────────── */
$('filterInput').oninput=()=>renderTable();

/* ── theme ─────────────────────────────────────────────────────────────── */
$('themeSelect').onchange=e=>{{
  document.body.className=e.target.value;
  if(e.target.value==='theme-light') document.documentElement.style.setProperty('--accent','#0284c7');
  else document.documentElement.style.setProperty('--accent',$('accentColor').value);
}};
$('accentColor').oninput=e=>document.documentElement.style.setProperty('--accent',e.target.value);

/* ── slider labels ─────────────────────────────────────────────────────── */
$('nodeSize').oninput=e=>$('nodeSizeVal').textContent=e.target.value;
$('forceRange').oninput=e=>$('forceVal').textContent=e.target.value;
$('linkDist').oninput=e=>$('linkDistVal').textContent=e.target.value;

/* ── actions ───────────────────────────────────────────────────────────── */
$('printBtn').onclick=()=>print();
$('jsonBtn').onclick=()=>{{
  const blob=new Blob([JSON.stringify(R.rawJson??R,null,2)],{{type:'application/json'}});
  const a=document.createElement('a'); a.href=URL.createObjectURL(blob);
  a.download='leakosint-report.json'; a.click(); URL.revokeObjectURL(a.href);
}};
$('copyBtn').onclick=async()=>{{
  try{{ await navigator.clipboard.writeText(location.href); $('copyBtn').textContent='✓ Copied!'; setTimeout(()=>{{ $('copyBtn').innerHTML='<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg> Copy link'; }},2000); }}catch{{}}
}};

}})();
</script>
</body>
</html>"""


def _query_from_graph(graph: dict[str, Any] | None) -> str:
    if not graph:
        return ""
    name = str(graph.get("name") or "")
    return name.split("-", 1)[-1].strip() if name else ""


def _style_value(style: str, key: str) -> str:
    match = re.search(rf"(?:^|,){re.escape(key)}:([^,]+)", style)
    return match.group(1).strip() if match else ""


def _record_label(record: dict[str, Any], index: int) -> str:
    for key in ("name", "full_name", "fio", "email", "phone", "username", "login"):
        for row_key, value in record.items():
            if key in str(row_key).lower() and value:
                return _short_value(value, 52)
    return f"Record #{index + 1}"


def _infer_type(key: Any, value: Any) -> str:
    text = f"{key} {value}".lower()
    if "@" in str(value):
        return "Email"
    if "phone" in text or re.fullmatch(r"[\d\s+().-]{7,}", str(value)):
        return "Phone"
    if "ip" in text and re.search(r"\d+\.\d+\.\d+\.\d+", str(value)):
        return "IP"
    if any(part in text for part in ("address", "city", "street", "region")):
        return "Address"
    if any(part in text for part in ("name", "fio", "surname")):
        return "Person"
    return "Custom"


def _type_color(key: Any, value: Any) -> str:
    return {
        "Email": "#38bdf8",
        "Phone": "#22c55e",
        "IP": "#fb7185",
        "Address": "#f59e0b",
        "Person": "#a78bfa",
    }.get(_infer_type(key, value), "#94a3b8")


def _short_value(value: Any, limit: int = 180) -> str:
    text = " ".join(str(value).split())
    return text if len(text) <= limit else text[: limit - 1] + "..."


def _safe_name(value: str) -> str:
    return (re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._") or "report")[:80]
