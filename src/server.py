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
# WEB UI + API
# ---------------------------------------------------------------------------

@mcp.custom_route("/", methods=["GET"])
async def web_ui(request: Request) -> HTMLResponse:
    html_path = WEB_DIR / "app.html"
    with open(html_path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> JSONResponse:
    return JSONResponse({"status": "ok", "server": "Parlamentaris Kompendium", "tools": 14})

@mcp.custom_route("/api/search", methods=["GET"])
async def api_search(request: Request) -> JSONResponse:
    q = request.query_params.get("q", "").strip()
    corpus = request.query_params.get("corpus", "hazszabaly")
    top_k = int(request.query_params.get("top_k", "8"))
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
