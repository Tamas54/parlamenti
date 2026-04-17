"""
Meta tool
=========
Információ a szerverről, adatforrásokról, verziókról.
"""

from pathlib import Path
import yaml

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "layer2"


def register_meta_tools(mcp: FastMCP) -> None:

    @mcp.tool
    def szerver_info() -> dict:
        """
        Információ a Parlamentaris Kompendium MCP szerverről:
        mit tartalmaz, milyen rétegek vannak, milyen verziójú a Házszabály.

        Használd ezt, ha tudni akarod, milyen kérdésekre tud válaszolni
        ez a szerver.
        """
        meta_path = DATA_DIR / "_meta.yaml"
        meta = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = yaml.safe_load(f) or {}

        return {
            "szerver": "Parlamentaris Kompendium",
            "verzio": "0.1.0 (Sprint 1 skeleton)",
            "celkitezes": (
                "Magyar Országgyűlési eljárásjogi tudásbázis nem-jogászoknak. "
                "A Házszabály, Alaptörvény parlamenti rendelkezései, OGY tv., "
                "és általános parlamenti jog precíziós lekérdezhetősége."
            ),
            "retegek": {
                "layer_0_altalanos": "Általános parlamenti jog (absztrakt, időtálló)",
                "layer_1_korpusz": "Teljes jogszabályi szövegek + vektoros RAG",
                "layer_2_strukturalt": "Időkeretek, határidők, folyamatok YAML-ban",
                "layer_3_precedens": "Frakciószabályok, elnöki döntvények, gyakorlat",
            },
            "adatforrasok": meta.get("adatforrasok", {
                "hazszabaly": "10/2014. (II.24.) OGY hat. — TÖLTÉS ALATT",
                "alaptorveny": "Magyarország Alaptörvénye — TÖLTÉS ALATT",
                "ogy_torveny": "2012. évi XXXVI. tv. — TÖLTÉS ALATT",
            }),
            "hogyan_kerdezz": [
                "Konkrét számhoz (perc, nap, fő): get_idokeret, get_hatarido",
                "Folyamat-leíráshoz: get_eljarasi_folyamat",
                "Szövegszerű kutatáshoz: search_hazszabaly, search_alaptorveny",
                "Szakszó-magyarázathoz: magyarazd_el",
                "Ha nem tudod honnan: search_all vagy list_* tool-ök",
            ],
            "figyelmezetes": (
                "Ez egy kutatási segédeszköz. Jogi állásfoglalásnak "
                "NEM minősül. Minden kritikus döntés előtt ellenőrizd "
                "a jogforrást a megadott hivatkozáson."
            ),
        }
