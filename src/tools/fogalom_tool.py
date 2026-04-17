"""
Fogalommagyarázó tool
=====================
Parlamenti szakszavak kezdőbarát magyarázata.
"""

from pathlib import Path
import yaml

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "layer2"


def _load_glosszarium() -> dict:
    path = DATA_DIR / "glosszarium.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def register_fogalom_tools(mcp: FastMCP) -> None:

    @mcp.tool
    def magyarazd_el(fogalom: str) -> dict:
        """
        Magyarázz el egy parlamenti szakszót kezdőbarát nyelven.

        Args:
            fogalom: Pl. "napirend_elotti", "vezerszonoklat",
                "interpellacio", "kerdes", "azonnali_kerdes",
                "jegyzokonyvi_hitelesitok", "hazelnok_helyettes",
                "korelnok", "hazbizottsag", "frakcio", "fuggetlen_kepviselo",
                "sarkalatos", "bizalmatlansag", "konstruktiv_bizalmatlansag"

        Returns:
            dict: rövid és részletes magyarázat, példa, jogforrás
        """
        data = _load_glosszarium()
        key = fogalom.lower().strip().replace(" ", "_")

        if key in data:
            return {"talalat": True, "fogalom": key, **data[key]}

        # Aliasokon is próbálkozunk
        for k, entry in data.items():
            aliases = [a.lower().replace(" ", "_") for a in entry.get("aliasok", [])]
            if key in aliases:
                return {"talalat": True, "fogalom": k, **entry}

        return {
            "talalat": False,
            "hiba": f"Nem ismert fogalom: '{fogalom}'",
            "tipp": (
                "Próbáld a list_fogalmak tool-t, vagy a search_all "
                "szemantikus keresőt."
            ),
        }

    @mcp.tool
    def list_fogalmak() -> list[str]:
        """
        Listázza az összes ismert parlamenti szakszót a glosszáriumban.
        """
        return sorted(_load_glosszarium().keys())
