"""
Parlamentaris Kompendium MCP Server
====================================
Magyar Országgyűlési eljárásjogi tudásbázis MCP-szerverként + webes kiskaté.

Transport: streamable HTTP (ChatGPT Developer Mode kompatibilis)
Web UI: / (interaktív kiskaté)
API: /api/* (REST végpontok a frontendhez)
MCP: /mcp (MCP protocol endpoint)
"""

import os
import logging
import yaml
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse

from tools.idokeret_tool import register_idokeret_tools
from tools.eljaras_tool import register_eljaras_tools
from tools.search_tool import register_search_tools
from tools.fogalom_tool import register_fogalom_tools
from tools.meta_tool import register_meta_tools
from tools.keret_tool import register_keret_tools

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("parlamentaris-mcp")

DATA_DIR = Path(__file__).resolve().parent / "data" / "layer2"
WEB_DIR = Path(__file__).resolve().parent / "web"

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

register_idokeret_tools(mcp)
register_eljaras_tools(mcp)
register_search_tools(mcp)
register_fogalom_tools(mcp)
register_meta_tools(mcp)
register_keret_tools(mcp)

# ---------------------------------------------------------------------------
# YAML LOADERS (shared by API routes)
# ---------------------------------------------------------------------------

def _load_yaml(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

# Lazy RAG engine singleton
_rag = None
def _get_rag():
    global _rag
    if _rag is None:
        from rag.engine import RAGEngine
        _rag = RAGEngine()
    return _rag

# ---------------------------------------------------------------------------
# ANALYTICS
# ---------------------------------------------------------------------------

STATS_KEY = os.getenv("STATS_KEY", "pk2026")
_BUD_TZ = timezone(timedelta(hours=2))
_visits: list[dict] = []  # in-memory, resets on deploy
_started = datetime.now(_BUD_TZ).isoformat()


def _track(request: Request, page: str):
    client = request.client
    ip = ""
    if client:
        ip = client.host or ""
    # Railway sets X-Forwarded-For
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    _visits.append({
        "t": datetime.now(_BUD_TZ).isoformat(timespec="seconds"),
        "page": page,
        "ip": ip,
        "ua": (request.headers.get("user-agent") or "")[:200],
        "ref": (request.headers.get("referer") or "")[:200],
        "lang": (request.headers.get("accept-language") or "")[:50],
    })
    # cap at 5000 entries
    if len(_visits) > 5000:
        del _visits[:1000]


# ---------------------------------------------------------------------------
# WEB UI + API
# ---------------------------------------------------------------------------

@mcp.custom_route("/", methods=["GET"])
async def web_ui(request: Request) -> HTMLResponse:
    _track(request, "/")
    html_path = WEB_DIR / "app.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "Parlamentaris Kompendium", "tools": 19})

@mcp.custom_route("/api/search", methods=["GET"])
async def api_search(request: Request) -> JSONResponse:
    q = request.query_params.get("q", "").strip()
    corpus = request.query_params.get("corpus", "hazszabaly")
    top_k = int(request.query_params.get("top_k", "8"))
    _track(request, f"/api/search?q={q}&corpus={corpus}")
    if not q:
        return JSONResponse([])
    engine = _get_rag()
    results = engine.search(q, corpus, top_k=top_k)
    return JSONResponse(results)

@mcp.custom_route("/api/fogalmak", methods=["GET"])
async def api_fogalmak(request: Request) -> JSONResponse:
    return JSONResponse(_load_yaml("glosszarium.yaml"))

@mcp.custom_route("/api/idokeretek", methods=["GET"])
async def api_idokeretek(request: Request) -> JSONResponse:
    return JSONResponse(_load_yaml("idokeretek.yaml"))

@mcp.custom_route("/api/szavazas", methods=["GET"])
async def api_szavazas(request: Request) -> JSONResponse:
    return JSONResponse(_load_yaml("szavazasi_szabalyok.yaml"))

@mcp.custom_route("/api/eljarasok", methods=["GET"])
async def api_eljarasok(request: Request) -> JSONResponse:
    return JSONResponse(_load_yaml("eljarasi_folyamatok.yaml"))

@mcp.custom_route("/api/keretek", methods=["GET"])
async def api_keretek(request: Request) -> JSONResponse:
    return JSONResponse(_load_yaml("kepviseloi_keretek.yaml"))

@mcp.custom_route("/api/bizottsagok", methods=["GET"])
async def api_bizottsagok(request: Request) -> JSONResponse:
    return JSONResponse(_load_yaml("bizottsagok.yaml"))


# ---------------------------------------------------------------------------
# STATS DASHBOARD (private)
# ---------------------------------------------------------------------------

@mcp.custom_route("/stats", methods=["GET"])
async def stats_dashboard(request: Request) -> HTMLResponse:
    key = request.query_params.get("key", "")
    if key != STATS_KEY:
        return HTMLResponse("<h1>403</h1>", status_code=403)

    now = datetime.now(_BUD_TZ)

    # unique IPs
    all_ips = set(v["ip"] for v in _visits if v["ip"])
    today_str = now.strftime("%Y-%m-%d")
    today_visits = [v for v in _visits if v["t"].startswith(today_str)]
    today_ips = set(v["ip"] for v in today_visits if v["ip"])

    # page hits
    page_counts = defaultdict(int)
    for v in _visits:
        p = v["page"]
        if p.startswith("/api/search"):
            p = "/api/search"
        page_counts[p] += 1

    # search queries
    searches = [v for v in _visits if v["page"].startswith("/api/search?q=")]
    search_queries = defaultdict(int)
    for v in searches:
        q = v["page"].split("q=")[1].split("&")[0] if "q=" in v["page"] else "?"
        search_queries[q] += 1
    top_queries = sorted(search_queries.items(), key=lambda x: -x[1])[:20]

    # referrers
    ref_counts = defaultdict(int)
    for v in _visits:
        r = v["ref"]
        if r:
            # extract domain
            try:
                parts = r.split("/")
                domain = parts[2] if len(parts) > 2 else r
            except Exception:
                domain = r
            ref_counts[domain] += 1
    top_refs = sorted(ref_counts.items(), key=lambda x: -x[1])[:15]

    # languages
    lang_counts = defaultdict(int)
    for v in _visits:
        lang = v["lang"].split(",")[0].split(";")[0].strip() if v["lang"] else "?"
        lang_counts[lang] += 1
    top_langs = sorted(lang_counts.items(), key=lambda x: -x[1])[:10]

    # hourly distribution (today)
    hourly = defaultdict(int)
    for v in today_visits:
        h = v["t"][11:13]
        hourly[h] += 1

    # recent visits
    recent = _visits[-30:][::-1]

    # Build HTML
    def row(label, val):
        return f'<tr><td style="color:#8b8fa0;padding:.3rem .5rem">{label}</td><td style="padding:.3rem .5rem;font-weight:600">{val}</td></tr>'

    def bar(label, count, max_count):
        pct = int(count / max(max_count, 1) * 100)
        return (f'<div style="display:flex;align-items:center;gap:.5rem;margin:.2rem 0">'
                f'<span style="min-width:120px;font-size:.8rem;color:#8b8fa0">{label}</span>'
                f'<div style="flex:1;background:#1c2029;border-radius:3px;height:18px">'
                f'<div style="width:{pct}%;background:#7c6cf0;border-radius:3px;height:18px"></div></div>'
                f'<span style="font-size:.8rem;min-width:30px">{count}</span></div>')

    stats_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stats</title>
<style>
body{{font-family:'Segoe UI',system-ui,sans-serif;background:#0c0e13;color:#e8e8ec;padding:1.5rem;max-width:800px;margin:0 auto}}
h1{{color:#e8b84b;font-size:1.3rem;margin-bottom:1rem}}
h2{{color:#7c6cf0;font-size:1rem;margin:1.5rem 0 .5rem;border-bottom:1px solid #262a36;padding-bottom:.3rem}}
table{{border-collapse:collapse;width:100%}}
.card{{background:#14171f;border:1px solid #262a36;border-radius:8px;padding:1rem;margin-bottom:.8rem}}
.grid{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:.6rem}}
.stat{{background:#14171f;border:1px solid #262a36;border-radius:8px;padding:.8rem;text-align:center}}
.stat-num{{font-size:1.8rem;font-weight:700;color:#e8b84b}}
.stat-label{{font-size:.75rem;color:#8b8fa0}}
.recent{{font-size:.75rem;max-height:400px;overflow-y:auto}}
.recent tr:nth-child(odd){{background:#14171f}}
.recent td{{padding:.25rem .4rem;white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis}}
</style></head><body>
<h1>Parlamentaris Kompendium — Analytics</h1>
<p style="font-size:.8rem;color:#8b8fa0">Szerver indul&aacute;s: {_started} | Most: {now.isoformat(timespec='seconds')}</p>

<div class="grid">
  <div class="stat"><div class="stat-num">{len(_visits)}</div><div class="stat-label">&ouml;sszes hit</div></div>
  <div class="stat"><div class="stat-num">{len(all_ips)}</div><div class="stat-label">unik&aacute;lis IP</div></div>
  <div class="stat"><div class="stat-num">{len(today_visits)}</div><div class="stat-label">mai hit</div></div>
</div>

<h2>Oldalak</h2>
<div class="card">{''.join(bar(p, c, max(page_counts.values()) if page_counts else 1) for p, c in sorted(page_counts.items(), key=lambda x: -x[1]))}</div>

<h2>Top keres&eacute;sek</h2>
<div class="card">{''.join(bar(q, c, max(x[1] for x in top_queries) if top_queries else 1) for q, c in top_queries) if top_queries else '<span style="color:#8b8fa0">M&eacute;g nincs keres&eacute;s</span>'}</div>

<h2>Honnan j&ouml;nnek (referrer)</h2>
<div class="card">{''.join(bar(r, c, max(x[1] for x in top_refs) if top_refs else 1) for r, c in top_refs) if top_refs else '<span style="color:#8b8fa0">Nincs referrer adat</span>'}</div>

<h2>Nyelvek</h2>
<div class="card">{''.join(bar(l, c, max(x[1] for x in top_langs) if top_langs else 1) for l, c in top_langs)}</div>

<h2>Mai &oacute;r&aacute;nk&eacute;nti eloszl&aacute;s</h2>
<div class="card">{''.join(bar(f'{h}:00', hourly.get(h,0), max(hourly.values()) if hourly else 1) for h in [f'{i:02d}' for i in range(24)] if hourly.get(h,0)>0) if hourly else '<span style="color:#8b8fa0">M&eacute;g nincs mai adat</span>'}</div>

<h2>Utols&oacute; 30 l&aacute;togat&aacute;s</h2>
<div class="card"><table class="recent"><tr style="color:#7c6cf0;font-size:.7rem"><td>Id&odblac;</td><td>Oldal</td><td>IP</td><td>Ref</td><td>Nyelv</td></tr>
{''.join(f"<tr><td>{v['t'][11:19]}</td><td>{v['page'][:40]}</td><td>{v['ip']}</td><td>{v['ref'][:30]}</td><td>{v['lang'][:10]}</td></tr>" for v in recent)}
</table></div>

</body></html>"""

    return HTMLResponse(stats_html)


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
