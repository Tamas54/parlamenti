"""
RAG Engine
==========
ChromaDB + sentence-transformers alapú szemantikus keresés.

Lazy init: a modell és a DB csak első használatkor töltődik be.
"""

import logging
import os
from pathlib import Path
from typing import Optional

log = logging.getLogger("parlamentaris-mcp.rag")

CHROMA_DIR = Path(__file__).resolve().parent.parent / "data" / "chroma"
CHUNKS_DIR = Path(__file__).resolve().parent.parent / "data" / "layer1_chunks"

# Jó magyar támogatás, kompakt modell
EMBED_MODEL = os.getenv(
    "EMBED_MODEL",
    "paraphrase-multilingual-MiniLM-L12-v2",
)


class RAGEngine:
    """Vektoros kereső a teljes jogszabályi korpuszon."""

    def __init__(self):
        self._client = None
        self._embedder = None
        self._collections = {}
        self._ready = False
        self._init_if_needed()

    def _init_if_needed(self):
        if self._ready:
            return
        try:
            import chromadb
            from chromadb.config import Settings
            from sentence_transformers import SentenceTransformer

            log.info("ChromaDB kliens indítása (%s)…", CHROMA_DIR)
            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(CHROMA_DIR),
                settings=Settings(anonymized_telemetry=False),
            )

            log.info("Embedding modell betöltése: %s", EMBED_MODEL)
            self._embedder = SentenceTransformer(EMBED_MODEL)

            self._ready = True
            log.info("RAG engine kész.")
        except Exception as e:  # pragma: no cover
            log.warning(
                "RAG engine nem tudott elindulni (%s). "
                "Valószínűleg még nincsenek adatok. "
                "Sprint 3-ban kap tartalmat.",
                e,
            )

    def _get_collection(self, name: str):
        if not self._ready:
            return None
        if name not in self._collections:
            try:
                self._collections[name] = self._client.get_collection(name)
            except Exception:
                log.warning("Collection '%s' nem létezik (még).", name)
                return None
        return self._collections[name]

    def search(
        self,
        query: str,
        collection: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Szemantikus keresés egy konkrét korpuszban."""
        if not self._ready:
            return [{
                "hiba": (
                    "RAG engine még nem áll készen. "
                    "A korpusz feltöltése Sprint 3-ban történik."
                ),
                "status": "skeleton",
            }]

        col = self._get_collection(collection)
        if col is None:
            return [{
                "hiba": f"A '{collection}' korpusz még nincs feltöltve.",
                "status": "empty",
            }]

        q_vec = self._embedder.encode([query]).tolist()
        res = col.query(
            query_embeddings=q_vec,
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

        out = []
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]

        for doc, meta, dist in zip(docs, metas, dists):
            out.append({
                "szoveg": doc,
                "hivatkozas": (meta or {}).get("hivatkozas"),
                "cim": (meta or {}).get("cim"),
                "forras": (meta or {}).get("forras"),
                "relevancia": round(1.0 - dist, 4),
            })
        return out
