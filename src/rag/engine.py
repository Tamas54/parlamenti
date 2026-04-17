"""
RAG Engine — Lightweight in-memory search
==========================================
TF-IDF alapú szemantikus keresés a teljes jogszabályi korpuszon.
Nincs szükség ChromaDB-re vagy GPU-ra — pure Python, gyors startup.

Korpuszok:
  - hazszabaly: Házszabály (egységes szerkezet, 10/2014 OGY hat. + Ogytv.)
  - alaptorveny: Magyarország Alaptörvénye
  - ogy_torveny: 2012. évi XXXVI. törvény (Ogytv.)
  - altalanos: (Sprint 3 — összehasonlító parlamenti jog)
"""

import json
import logging
import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

log = logging.getLogger("parlamentaris-mcp.rag")

CHUNKS_DIR = Path(__file__).resolve().parent.parent / "data" / "layer1_chunks"

# Hungarian stop words (frequent words that don't help search)
STOP_WORDS = {
    "a", "az", "es", "is", "van", "volt", "nem", "hogy", "egy", "ez",
    "meg", "de", "ha", "mint", "vagy", "sem", "meg", "mar",
    "csak", "fel", "ki", "le", "be", "el", "ra", "ide", "oda",
    "amely", "amelyet", "amelynek", "amit", "aki", "akit", "akinek",
    "illetve", "valamint", "tovabba", "illetoleg", "szerinti", "szerint",
    "alapjan", "ertelmeben", "vonatkozo", "vonatkozoan", "eseteben",
    "tekinteteben", "kereteben", "erdekeben", "celbol", "szemben",
}


def _strip_accents(text: str) -> str:
    """Remove Hungarian accents for accent-insensitive matching."""
    # Handle Hungarian double-acute (ő, ű) specially
    text = text.replace('ő', 'o').replace('Ő', 'O')
    text = text.replace('ű', 'u').replace('Ű', 'U')
    nfkd = unicodedata.normalize('NFKD', text)
    return ''.join(c for c in nfkd if not unicodedata.combining(c))


def _tokenize(text: str) -> list[str]:
    """Hungarian tokenizer: lowercase, strip accents, split on non-alpha."""
    text = _strip_accents(text.lower())
    tokens = re.findall(r'[a-z]+', text)
    return [t for t in tokens if len(t) > 2 and t not in STOP_WORDS]


class TFIDFIndex:
    """Lightweight TF-IDF index for Hungarian legal text search."""

    def __init__(self):
        self.docs: list[dict] = []       # original chunk dicts
        self.tokens: list[list[str]] = [] # tokenized docs
        self.idf: dict[str, float] = {}   # inverse document frequency
        self._built = False

    def add_docs(self, chunks: list[dict], text_key: str = "szoveg"):
        for chunk in chunks:
            self.docs.append(chunk)
            self.tokens.append(_tokenize(chunk.get(text_key, "")))

    def build(self):
        """Compute IDF scores."""
        n = len(self.docs)
        if n == 0:
            return
        df = Counter()
        for toks in self.tokens:
            for term in set(toks):
                df[term] += 1
        self.idf = {
            term: math.log((n + 1) / (count + 1)) + 1
            for term, count in df.items()
        }
        self._built = True
        log.info("TF-IDF index built: %d docs, %d terms", n, len(self.idf))

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Search using TF-IDF cosine-ish scoring."""
        if not self._built:
            return []
        q_tokens = _tokenize(query)
        if not q_tokens:
            return []

        q_tf = Counter(q_tokens)
        q_vec = {t: q_tf[t] * self.idf.get(t, 1.0) for t in q_tokens}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scores = []
        for i, doc_tokens in enumerate(self.tokens):
            if not doc_tokens:
                continue
            d_tf = Counter(doc_tokens)
            dot = 0.0
            for t, q_w in q_vec.items():
                if t in d_tf:
                    d_w = d_tf[t] * self.idf.get(t, 1.0)
                    dot += q_w * d_w
            if dot > 0:
                d_norm = math.sqrt(
                    sum((d_tf[t] * self.idf.get(t, 1.0)) ** 2 for t in d_tf)
                ) or 1.0
                score = dot / (q_norm * d_norm)
                scores.append((score, i))

        scores.sort(reverse=True)
        results = []
        for score, idx in scores[:top_k]:
            doc = self.docs[idx]
            results.append({
                "szoveg": doc.get("szoveg", ""),
                "hivatkozas": doc.get("hivatkozas", ""),
                "cim": doc.get("cim", doc.get("cikk", "")),
                "forras": doc.get("forras", ""),
                "relevancia": round(score, 4),
            })
        return results


class RAGEngine:
    """Keresőmotor a teljes jogszabályi korpuszra."""

    COLLECTION_MAP = {
        "hazszabaly": "hazszabaly_chunks.json",
        "alaptorveny": "alaptorveny_chunks.json",
        "ogy_torveny": "ogytv_chunks.json",
    }

    def __init__(self):
        self._indices: dict[str, TFIDFIndex] = {}
        self._ready = False
        self._init()

    def _init(self):
        loaded = 0
        for name, filename in self.COLLECTION_MAP.items():
            path = CHUNKS_DIR / filename
            if not path.exists():
                log.warning("Chunk file not found: %s", path)
                continue
            with open(path, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            idx = TFIDFIndex()
            idx.add_docs(chunks)
            idx.build()
            self._indices[name] = idx
            loaded += len(chunks)
            log.info("Loaded %s: %d chunks", name, len(chunks))

        if loaded > 0:
            self._ready = True
            log.info("RAG engine ready: %d total chunks across %d collections",
                     loaded, len(self._indices))
        else:
            log.warning("RAG engine: no chunks loaded.")

    def search(
        self,
        query: str,
        collection: str,
        top_k: int = 5,
    ) -> list[dict]:
        if not self._ready:
            return [{
                "hiba": "RAG engine nem áll készen — nincsenek betöltve a szövegek.",
                "status": "no_data",
            }]

        idx = self._indices.get(collection)
        if idx is None:
            return [{
                "hiba": f"A '{collection}' korpusz nem létezik.",
                "elerheto": list(self._indices.keys()),
                "status": "not_found",
            }]

        results = idx.search(query, top_k=top_k)
        if not results:
            return [{
                "hiba": "Nincs találat a keresési kifejezésre.",
                "tipp": "Próbálj másképp fogalmazni, vagy használd a search_all tool-t.",
                "status": "no_results",
            }]
        return results
