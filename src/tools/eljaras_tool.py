"""
Eljárási folyamat tool
======================
Lépésről lépésre leírja a különböző parlamenti folyamatokat.
"""

from pathlib import Path
from typing import Optional
import yaml

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "layer2"


def _load_folyamatok() -> dict:
    path = DATA_DIR / "eljarasi_folyamatok.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def register_eljaras_tools(mcp: FastMCP) -> None:

    @mcp.tool
    def get_eljarasi_folyamat(
        tipus: str,
        reszletesseg: str = "normal",
    ) -> dict:
        """
        Lépésről lépésre leírja a parlamenti folyamatokat.

        Args:
            tipus: Milyen folyamat? Pl.:
                "alakulo_ules" - az OGY alakuló ülése
                "altalanos_ules" - átlagos ülésnap menete
                "torvenyalkotasi_eljaras" - egy törvény útja benyújtástól kihirdetésig
                "kivetel_targyalas" - kivételes eljárás
                "sarkalatos_torveny" - 2/3-os törvény menete
                "bizalmi_szavazas" - bizalmi/bizalmatlansági indítvány
                "interpellacio_menete"
                "kerdes_menete"
                "napirend_elotti_menete"
                "napirend_utani_menete"
            reszletesseg: "rovid" | "normal" | "reszletes"

        Returns:
            dict: lépéslista, szereplők, időkeretek, jogforrás
        """
        data = _load_folyamatok()
        key = tipus.lower().strip()

        if key not in data:
            return {
                "talalat": False,
                "hiba": f"Nem ismert eljárás típus: '{tipus}'",
                "elerheto_tipusok": sorted(data.keys()),
            }

        entry = data[key]

        if reszletesseg == "rovid":
            # Csak a fő lépések címei
            return {
                "talalat": True,
                "tipus": key,
                "nev": entry.get("nev"),
                "leiras_rovid": entry.get("leiras_rovid"),
                "lepesek_cimei": [
                    l.get("cim", "") for l in entry.get("lepesek", [])
                ],
                "jogforras": entry.get("jogforras"),
            }

        return {"talalat": True, "tipus": key, **entry}

    @mcp.tool
    def list_eljarasi_folyamatok() -> list[dict]:
        """
        Listázza az összes ismert parlamenti folyamatot rövid leírással.
        """
        data = _load_folyamatok()
        return [
            {
                "tipus": key,
                "nev": entry.get("nev", key),
                "leiras_rovid": entry.get("leiras_rovid", ""),
            }
            for key, entry in sorted(data.items())
        ]

    @mcp.tool
    def get_szavazasi_szabalyok(targykor: str) -> dict:
        """
        Milyen többség kell? Nyílt vagy titkos szavazás?

        Args:
            targykor: Pl. "sarkalatos_torveny", "egyszeru_torveny",
                "hazszabaly_modositas", "alkotmany_modositas",
                "koztarsasagi_elnok_valasztas", "bizalmatlansag",
                "haborus_helyzet", "alkotmanybiro_valasztas"

        Returns:
            dict: szükséges többség, szavazási mód, jogforrás
        """
        path = DATA_DIR / "szavazasi_szabalyok.yaml"
        if not path.exists():
            return {"talalat": False, "hiba": "Nincs betöltve szavazási tábla."}
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        key = targykor.lower().strip()
        if key not in data:
            return {
                "talalat": False,
                "hiba": f"Nem ismert tárgykör: '{targykor}'",
                "elerheto_targykorok": sorted(data.keys()),
            }
        return {"talalat": True, "targykor": key, **data[key]}
