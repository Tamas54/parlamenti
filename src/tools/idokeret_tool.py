"""
Időkeret tool
=============
Felszólalási idők, időkeretek pontos lekérdezése.

NINCS RAG. Strukturált YAML-ból olvas, hogy ne hallucináljon a számok körül.
Minden válasz mellett jogszabályi hivatkozás (Házszabály §-ra).
"""

from pathlib import Path
from typing import Optional
import yaml

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "layer2"


def _load_idokeretek() -> dict:
    """Betölti az időkeret YAML-okat."""
    path = DATA_DIR / "idokeretek.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def register_idokeret_tools(mcp: FastMCP) -> None:

    @mcp.tool
    def get_idokeret(
        szituacio: str,
        szereplo: Optional[str] = None,
    ) -> dict:
        """
        Felszólalási időkeretet ad meg pontos számmal, szabályhivatkozással.

        Args:
            szituacio: A parlamenti helyzet, pl.:
                "napirend_elotti", "napirend_utani", "interpellacio",
                "azonnali_kerdes", "kerdes", "vezerszonoklat",
                "vita", "szemelyes_nyilatkozat", "ugyrendi_felszolalas"
            szereplo: Ki szólal fel? Pl.:
                "miniszterelnok", "miniszter", "frakciovezeto",
                "frakcioszonok", "kepviselo", "nemzetisegi_szoszolo"

        Returns:
            dict: időkeret, válasz-jog, különleges szabályok, jogforrás
        """
        data = _load_idokeretek()
        key = szituacio.lower().strip()

        if key not in data:
            available = sorted(data.keys())
            return {
                "talalat": False,
                "hiba": f"Nem ismert szituáció: '{szituacio}'",
                "elerheto_szituaciok": available,
                "javaslat": (
                    "Próbáld az elérhető szituációk egyikét, vagy használd a "
                    "search_hazszabaly tool-t."
                ),
            }

        entry = data[key]

        # Ha szereplő is meg van adva, szűkítünk
        if szereplo:
            szereplok = entry.get("szereplok", {})
            sz_key = szereplo.lower().strip()
            if sz_key in szereplok:
                result = {
                    "talalat": True,
                    "szituacio": key,
                    "szereplo": sz_key,
                    **szereplok[sz_key],
                    "jogforras": entry.get("jogforras"),
                    "megjegyzes": entry.get("megjegyzes"),
                }
                return result
            return {
                "talalat": False,
                "hiba": f"Nem ismert szereplő: '{szereplo}'",
                "elerheto_szereplok": list(szereplok.keys()),
                "altalanos_szabaly": entry.get("altalanos"),
                "jogforras": entry.get("jogforras"),
            }

        # Ha csak szituáció van, az egész blokkot visszaadjuk
        return {
            "talalat": True,
            "szituacio": key,
            **entry,
        }

    @mcp.tool
    def get_hatarido(esemeny: str) -> dict:
        """
        Benyújtási, válaszadási, kézbesítési határidőket ad meg.

        Args:
            esemeny: Pl. "modosito_inditvany", "kapcsolodo_modosito",
                "kerdes_valasz", "interpellacio_valasz",
                "napirend_kezbesites", "bizottsagi_allaspont"

        Returns:
            dict: határidő, számítási mód, jogforrás
        """
        path = DATA_DIR / "hatarido_tabla.yaml"
        if not path.exists():
            return {"talalat": False, "hiba": "Nincs betöltve határidő-tábla."}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        key = esemeny.lower().strip()
        if key not in data:
            return {
                "talalat": False,
                "hiba": f"Nem ismert esemény: '{esemeny}'",
                "elerheto_esemenyek": sorted(data.keys()),
            }
        return {"talalat": True, "esemeny": key, **data[key]}

    @mcp.tool
    def list_idokeret_szituaciok() -> list[str]:
        """
        Listázza az összes ismert parlamenti szituációt, amire van időkeret adat.
        Használd ezt, ha nem vagy biztos a paraméter-névben.
        """
        return sorted(_load_idokeretek().keys())
