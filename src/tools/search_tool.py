"""
Szemantikus keresés (RAG) tool
==============================
Vektoros keresés a teljes szövegkorpuszon (Alaptörvény, Házszabály, OGY tv.,
általános parlamenti jogi réteg).

A kereső ChromaDB + multilingual sentence-transformer modellt használ.
Lazy init: csak az első hívásnál tölti be a modellt (kímélve a cold start-ot).
"""

from pathlib import Path
from typing import Optional
import logging

from fastmcp import FastMCP

log = logging.getLogger("parlamentaris-mcp.search")

_engine = None  # lazy singleton


def _get_engine():
    """Lazy-init a RAG motor. Csak első hívásnál tölt modellt + ChromaDB-t."""
    global _engine
    if _engine is None:
        from rag.engine import RAGEngine
        log.info("RAG engine első inicializálása…")
        _engine = RAGEngine()
    return _engine


def register_search_tools(mcp: FastMCP) -> None:

    @mcp.tool
    def search_hazszabaly(
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Szemantikus keresés a HÁZSZABÁLY szövegében
        (10/2014. (II.24.) OGY határozat, hatályos változat).

        Args:
            query: A keresési kérdés természetes nyelven
            top_k: Hány találatot adjon (alapértelmezett: 5)

        Returns:
            list[dict]: találatok, releváns §-okkal, kontextussal
        """
        engine = _get_engine()
        return engine.search(
            query=query,
            collection="hazszabaly",
            top_k=top_k,
        )

    @mcp.tool
    def search_alaptorveny(
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Szemantikus keresés az ALAPTÖRVÉNYBEN.
        Hasznos például: alapjogok, parlamenti felhatalmazások, ciklus,
        köztársasági elnök, Alkotmánybíróság, különleges jogrend.

        Args:
            query: A keresési kérdés természetes nyelven
            top_k: Hány találatot adjon (alapértelmezett: 5)
        """
        engine = _get_engine()
        return engine.search(
            query=query,
            collection="alaptorveny",
            top_k=top_k,
        )

    @mcp.tool
    def search_ogy_torveny(
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Szemantikus keresés a 2012. évi XXXVI. törvényben (Országgyűlésről).
        A képviselői jogállás, összeférhetetlenség, mentelmi jog kérdéseihez.
        """
        engine = _get_engine()
        return engine.search(
            query=query,
            collection="ogy_torveny",
            top_k=top_k,
        )

    @mcp.tool
    def search_altalanos_parlamenti_jog(
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """
        Szemantikus keresés az ÁLTALÁNOS parlamenti jogi rétegben.
        Ez a réteg absztraktabb, időtállóbb: parlamentarizmus alapelvei,
        összehasonlító parlamenti jog, bevett eljárási gyakorlat,
        jogtudományi magyarázatok.

        Hasznos, ha a kérdés elvi jellegű, vagy a konkrét Házszabály
        nem ad egyértelmű választ.
        """
        engine = _get_engine()
        return engine.search(
            query=query,
            collection="altalanos",
            top_k=top_k,
        )

    @mcp.tool
    def search_all(
        query: str,
        top_k: int = 8,
    ) -> dict:
        """
        Egyszerre keres az összes korpuszban.
        Használd ezt, ha nem tudod pontosan hol van a válasz.

        Returns:
            dict: találatok korpuszonként csoportosítva
        """
        engine = _get_engine()
        return {
            "hazszabaly": engine.search(query, "hazszabaly", top_k=top_k // 2),
            "alaptorveny": engine.search(query, "alaptorveny", top_k=top_k // 4),
            "ogy_torveny": engine.search(query, "ogy_torveny", top_k=top_k // 4),
            "altalanos": engine.search(query, "altalanos", top_k=top_k // 4),
        }
