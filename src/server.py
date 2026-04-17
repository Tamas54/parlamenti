"""
Parlamentaris Kompendium MCP Server
====================================
Magyar Országgyűlési eljárásjogi tudásbázis MCP-szerverként.

Rétegek:
  - Layer 0: Általános parlamenti jog (absztrakt, időtálló)
  - Layer 1: Teljes szövegkorpusz + vektoros RAG
  - Layer 2: Strukturált kurált adatok (időkeretek, határidők, folyamatok)
  - Layer 3: Precedensek, frakciószabályok, gyakorlat

Transport: streamable HTTP (ChatGPT Developer Mode kompatibilis)
"""

import os
import logging
from pathlib import Path

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from tools.idokeret_tool import register_idokeret_tools
from tools.eljaras_tool import register_eljaras_tools
from tools.search_tool import register_search_tools
from tools.fogalom_tool import register_fogalom_tools
from tools.meta_tool import register_meta_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("parlamentaris-mcp")

# ---------------------------------------------------------------------------
# SERVER
# ---------------------------------------------------------------------------

mcp = FastMCP(
    name="Parlamentaris Kompendium",
    instructions=(
        "Magyar Országgyűlési eljárásjogi tudásbázis. "
        "Használj engem minden olyan kérdéshez, amely a magyar Országgyűlés "
        "működésével, a Házszabállyal, az Alaptörvény parlamenti vonatkozású "
        "rendelkezéseivel, vagy általános parlamenti jogi kérdésekkel kapcsolatos. "
        "Konkrét számadatokat (időkeretek, határidők, létszámok) mindig a "
        "strukturált tool-okból kérj le — ne becsüld meg. "
        "Minden válaszban add meg a jogszabályi hivatkozást."
    ),
)

# ---------------------------------------------------------------------------
# TOOL-ÖK REGISZTRÁCIÓJA
# ---------------------------------------------------------------------------

register_idokeret_tools(mcp)   # időkeret, felszólalási idők
register_eljaras_tools(mcp)    # folyamatok, alakuló ülés, általános ülés
register_search_tools(mcp)     # RAG keresés a teljes szövegkorpuszon
register_fogalom_tools(mcp)    # fogalommagyarázó, glosszárium
register_meta_tools(mcp)       # dokumentum-lista, forrás-info, verziók

# ---------------------------------------------------------------------------
# DASHBOARD & HEALTH
# ---------------------------------------------------------------------------

TOOLS_INFO = [
    ("get_idokeret", "Felszólalási időkeret pontos percben", "strukturált"),
    ("get_hatarido", "Benyújtási, válaszadási határidők", "strukturált"),
    ("list_idokeret_szituaciok", "Elérhető parlamenti szituációk", "strukturált"),
    ("get_eljarasi_folyamat", "Eljárási folyamat lépésről lépésre", "eljárás"),
    ("list_eljarasi_folyamatok", "Folyamatok katalógusa", "eljárás"),
    ("get_szavazasi_szabalyok", "Szavazási többségi követelmények", "eljárás"),
    ("search_hazszabaly", "Házszabály RAG keresés", "RAG"),
    ("search_alaptorveny", "Alaptörvény RAG keresés", "RAG"),
    ("search_ogy_torveny", "OGY tv. RAG keresés", "RAG"),
    ("search_altalanos_parlamenti_jog", "Általános parlamenti jog RAG", "RAG"),
    ("search_all", "Keresés minden korpuszban", "RAG"),
    ("magyarazd_el", "Szakszó-magyarázat kezdőbarát nyelven", "fogalomtár"),
    ("list_fogalmak", "Glosszárium tartalma", "fogalomtár"),
    ("szerver_info", "Szerver és adatforrás infó", "meta"),
]

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Parlamentaris Kompendium MCP</title>
<style>
  :root {
    --bg: #0f1117;
    --surface: #1a1d27;
    --border: #2a2d3a;
    --text: #e4e4e7;
    --muted: #9ca3af;
    --accent: #c084fc;
    --accent2: #818cf8;
    --green: #4ade80;
    --tag-struct: #fbbf24;
    --tag-eljaras: #60a5fa;
    --tag-rag: #a78bfa;
    --tag-fogalom: #34d399;
    --tag-meta: #9ca3af;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--text);
    min-height: 100vh;
    padding: 2rem 1rem;
  }
  .container { max-width: 900px; margin: 0 auto; }
  header {
    text-align: center;
    margin-bottom: 3rem;
    padding: 2.5rem 2rem;
    background: linear-gradient(135deg, rgba(129,140,248,0.08), rgba(192,132,252,0.08));
    border: 1px solid var(--border);
    border-radius: 16px;
  }
  .magyar-cimer {
    font-size: 3rem;
    margin-bottom: 0.5rem;
  }
  h1 {
    font-size: 1.8rem;
    font-weight: 700;
    background: linear-gradient(135deg, var(--accent2), var(--accent));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5rem;
  }
  .subtitle { color: var(--muted); font-size: 0.95rem; }
  .status-bar {
    display: flex;
    gap: 1.5rem;
    justify-content: center;
    flex-wrap: wrap;
    margin-top: 1.5rem;
  }
  .status-item {
    display: flex;
    align-items: center;
    gap: 0.4rem;
    font-size: 0.85rem;
    color: var(--muted);
  }
  .dot { width: 8px; height: 8px; border-radius: 50%; }
  .dot-green { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .dot-yellow { background: var(--tag-struct); }

  .section-title {
    font-size: 1.1rem;
    font-weight: 600;
    margin-bottom: 1rem;
    color: var(--accent);
  }

  .layers {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 0.75rem;
    margin-bottom: 2.5rem;
  }
  .layer-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 1rem;
  }
  .layer-num {
    font-size: 0.75rem;
    font-weight: 700;
    color: var(--accent2);
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
  .layer-name {
    font-weight: 600;
    font-size: 0.9rem;
    margin: 0.3rem 0;
  }
  .layer-desc { font-size: 0.8rem; color: var(--muted); }

  .tools-grid {
    display: grid;
    gap: 0.5rem;
    margin-bottom: 2.5rem;
  }
  .tool-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 0.65rem 1rem;
    transition: border-color 0.15s;
  }
  .tool-row:hover { border-color: var(--accent); }
  .tool-name {
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
    font-size: 0.85rem;
    font-weight: 600;
    min-width: 280px;
    color: var(--accent2);
  }
  .tool-desc { font-size: 0.8rem; color: var(--muted); flex: 1; }
  .tag {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.15rem 0.5rem;
    border-radius: 4px;
    text-transform: uppercase;
    letter-spacing: 0.3px;
    white-space: nowrap;
  }
  .tag-strukturalt { background: rgba(251,191,36,0.15); color: var(--tag-struct); }
  .tag-eljaras { background: rgba(96,165,250,0.15); color: var(--tag-eljaras); }
  .tag-rag { background: rgba(167,139,250,0.15); color: var(--tag-rag); }
  .tag-fogalomtar { background: rgba(52,211,153,0.15); color: var(--tag-fogalom); }
  .tag-meta { background: rgba(156,163,175,0.15); color: var(--tag-meta); }

  .connect-box {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 1.5rem;
    margin-bottom: 2rem;
  }
  .connect-box h3 {
    font-size: 0.95rem;
    margin-bottom: 0.75rem;
    color: var(--accent);
  }
  code {
    background: rgba(129,140,248,0.1);
    padding: 0.15rem 0.4rem;
    border-radius: 4px;
    font-size: 0.85rem;
    color: var(--accent2);
    font-family: 'JetBrains Mono', 'Fira Code', monospace;
  }
  .url-box {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.6rem 1rem;
    margin-top: 0.5rem;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.85rem;
    color: var(--green);
    word-break: break-all;
  }
  .steps { padding-left: 1.2rem; }
  .steps li { margin-bottom: 0.4rem; font-size: 0.85rem; color: var(--muted); }
  footer {
    text-align: center;
    padding-top: 2rem;
    font-size: 0.75rem;
    color: var(--muted);
    border-top: 1px solid var(--border);
  }
  @media (max-width: 600px) {
    .tool-row { flex-direction: column; align-items: flex-start; gap: 0.3rem; }
    .tool-name { min-width: auto; }
  }
</style>
</head>
<body>
<div class="container">

<header>
  <div class="magyar-cimer">\U0001f3db\ufe0f</div>
  <h1>Parlamentaris Kompendium</h1>
  <p class="subtitle">Magyar Orsz\u00e1ggy\u0171l\u00e9si elj\u00e1r\u00e1sjogi tud\u00e1sb\u00e1zis \u2014 MCP szerver</p>
  <div class="status-bar">
    <div class="status-item"><span class="dot dot-green"></span> MCP szerver akt\u00edv</div>
    <div class="status-item"><span class="dot dot-green"></span> 14 tool regisztr\u00e1lva</div>
    <div class="status-item"><span class="dot dot-yellow"></span> RAG: Sprint 3</div>
    <div class="status-item">v0.1.0</div>
  </div>
</header>

<div class="section-title">Tud\u00e1sr\u00e9tegek</div>
<div class="layers">
  <div class="layer-card">
    <div class="layer-num">Layer 0</div>
    <div class="layer-name">\u00c1ltal\u00e1nos parlamenti jog</div>
    <div class="layer-desc">Absztrakt, id\u0151t\u00e1ll\u00f3 jogtudom\u00e1nyi r\u00e9teg</div>
  </div>
  <div class="layer-card">
    <div class="layer-num">Layer 1</div>
    <div class="layer-name">Sz\u00f6vegkorpusz (RAG)</div>
    <div class="layer-desc">Alapt\u00f6rv\u00e9ny, H\u00e1zszab\u00e1ly, OGY tv. \u2014 szemantikus keres\u00e9s</div>
  </div>
  <div class="layer-card">
    <div class="layer-num">Layer 2</div>
    <div class="layer-name">Struktur\u00e1lt adatok</div>
    <div class="layer-desc">Id\u0151keretek, hat\u00e1rid\u0151k, szavaz\u00e1si szab\u00e1lyok YAML-ban</div>
  </div>
  <div class="layer-card">
    <div class="layer-num">Layer 3</div>
    <div class="layer-name">Precedensek</div>
    <div class="layer-desc">Frakci\u00f3szab\u00e1lyok, eln\u00f6ki d\u00f6ntv\u00e9nyek, gyakorlat</div>
  </div>
</div>

<div class="section-title">Tool-\u00f6k (14 db)</div>
<div class="tools-grid">
  TOOLS_ROWS_PLACEHOLDER
</div>

<div class="connect-box">
  <h3>Csatlakoz\u00e1s</h3>
  <p style="font-size:0.85rem; color:var(--muted); margin-bottom:0.5rem;">
    Ez egy <strong>MCP szerver</strong> \u2014 ChatGPT, Claude, vagy b\u00e1rmely MCP-kompatibilis klienssel haszn\u00e1lhat\u00f3.
  </p>
  <div><strong style="font-size:0.8rem;">MCP Endpoint:</strong></div>
  <div class="url-box" id="mcp-url"></div>

  <h3 style="margin-top:1.2rem;">ChatGPT be\u00e1ll\u00edt\u00e1s</h3>
  <ol class="steps">
    <li>Settings \u2192 Connectors \u2192 Developer Mode: ON</li>
    <li>Add new connector \u2192 MCP Server URL: <em>(a fenti URL)</em></li>
    <li>Authentication: None</li>
    <li>\u00daj chatben: + men\u00fc \u2192 Developer mode \u2192 Parlamentaris Kompendium</li>
  </ol>
</div>

<footer>
  Kutat\u00e1si seg\u00e9deszk\u00f6z \u2014 jogi \u00e1ll\u00e1sfoglal\u00e1snak NEM min\u0151s\u00fcl.<br>
  MIT licenc &middot; Parlamentaris Kompendium v0.1.0
</footer>

</div>
<script>
  document.getElementById('mcp-url').textContent = location.origin + '/mcp';
</script>
</body>
</html>"""


def _build_dashboard_html() -> str:
    rows = []
    tag_map = {
        "strukturált": "strukturalt",
        "eljárás": "eljaras",
        "RAG": "rag",
        "fogalomtár": "fogalomtar",
        "meta": "meta",
    }
    for name, desc, category in TOOLS_INFO:
        tag_cls = tag_map.get(category, "meta")
        rows.append(
            f'<div class="tool-row">'
            f'<span class="tool-name">{name}</span>'
            f'<span class="tool-desc">{desc}</span>'
            f'<span class="tag tag-{tag_cls}">{category}</span>'
            f'</div>'
        )
    return DASHBOARD_HTML.replace("TOOLS_ROWS_PLACEHOLDER", "\n  ".join(rows))


@mcp.custom_route("/", methods=["GET"])
async def dashboard(request: Request) -> HTMLResponse:
    return HTMLResponse(_build_dashboard_html())


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "Parlamentaris Kompendium", "tools": 14})


# ---------------------------------------------------------------------------
# STARTUP
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    log.info("Parlamentaris Kompendium MCP indul…")
    log.info("  → host=%s  port=%s", host, port)
    log.info("  → transport=streamable-http")

    mcp.run(
        transport="http",
        host=host,
        port=port,
    )
