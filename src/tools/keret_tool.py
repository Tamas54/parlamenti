"""
Képviselői keretek tool
=======================
Tiszteletdíj, iroda, munkatárs, üzemanyag, lakhatás, mobil,
frakciós keretek strukturált lekérdezése.

NINCS RAG. Strukturált YAML-ból olvas, hogy ne hallucináljon a számok körül.
Minden válasz mellett jogszabályi hivatkozás (Ogytv. §-ra).

ADATOK ÉRVÉNYESSÉGE: 2026. március 1. – 2027. február 28.
T (tiszteletdíj-alap) = 2 182 488 Ft (OGYH 2026-03-01 táblázat alapján,
KSH bruttó átlagkereset 727 496 Ft × 3). FIGYELEM: az OGYH által alkalmazott
KSH-mutató NEM azonos a KSH-gyorstájékoztatókból látható nyers
nemzetgazdasági átlaggal (~705 000 Ft), hanem egy magasabb, specifikus
indikátor. A korábbi 704 937 Ft / 2 114 811 Ft bázis (2026-04 előtti
YAML-verzió) téves volt, a 2026-04 audit korrigálta.
"""

from pathlib import Path
from typing import Optional
import yaml

from fastmcp import FastMCP

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "layer2"

# Kategóriák, amelyeket külön-külön listázhatunk
_EGYENI_KULCSOK = [
    "iroda_keret",
    "munkatarsi_keret",
    "uzemanyag_keret",
    "lakhatas_keret",
    "mobil_keret",
    "ingyenes_szolgaltatasok",
    "nemzetisegi_bizottsagi_keret",
]

_FRAKCIO_KULCSOK = [
    "frakcio_alapkeret",
    "frakcio_fejkvota",
    "kozos_listas_alapkeret",
    "fuggetlen_kepviselo_keret",
    "frakcio_berkeret",
    "frakcios_iroda",
    "irodafenntartas_dologi_keret",
]

_PUHA_KULCSOK = [
    "iroda_atruhazas",
    "munkatars_rendelkezes_atruhazas",
    "keretmaradvany_automatikus_atszallas",
    "frakciora_terhelt_egyeni_jogcimek",
    "kapcsolodo_finanszirozas",
]

_SZANKCIO_KULCSOK = [
    "ajandek_limit",
    "tiszteletdij_csokkentes",
    "mandatumvegi_ellatas",
]


def _load_keretek() -> dict:
    path = DATA_DIR / "kepviseloi_keretek.yaml"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _kozelito_figyelmeztetes(data: dict) -> str:
    """Megjegyzés a KSH-bázis és T értékéről — forrás, érvényesség."""
    alap = data.get("alap_szamok", {})
    return alap.get(
        "ksh_kozelito_jelleg",
        (
            "FIGYELEM: a T (2 182 488 Ft) alapjául szolgáló KSH-mutató nem "
            "azonos a KSH-gyorstájékoztatókból látható nyers nemzetgazdasági "
            "átlaggal — a törvény egy specifikus, magasabb mutatót használ."
        ),
    ).strip()


def register_keret_tools(mcp: FastMCP) -> None:

    @mcp.tool
    def get_kepviseloi_keret(kategoria: str) -> dict:
        """
        Képviselői / frakciós keret adatait adja vissza — pontos forintösszeggel,
        jogszabályi hivatkozással.

        FIGYELEM: a T (tiszteletdíj-alap) a 2025. évi KSH bruttó átlagkereset
        12 havi számtani átlagán alapul — KÖZELÍTŐ ÉRTÉK. Minden ebből
        számolt összeg (iroda, munkatárs, bérkeret stb.) ugyanolyan mértékben
        közelítő, a hivatalos KSH-közzététel véglegesítésekor pontosodhat.

        Args:
            kategoria: A keret azonosítója. Pl.:
                - alap_szamok, tiszteletdij
                - iroda_keret, munkatarsi_keret, uzemanyag_keret,
                  lakhatas_keret, mobil_keret, ingyenes_szolgaltatasok,
                  nemzetisegi_bizottsagi_keret
                - frakcio_alapkeret, frakcio_fejkvota, kozos_listas_alapkeret,
                  fuggetlen_kepviselo_keret, frakcio_berkeret, frakcios_iroda
                - ajandek_limit, tiszteletdij_csokkentes, mandatumvegi_ellatas
                - gazdalkodas

        Returns:
            dict: a keret teljes adatblokkja + jogforras + kozelito figyelmeztetés
        """
        data = _load_keretek()
        key = kategoria.lower().strip()

        if key not in data:
            return {
                "talalat": False,
                "hiba": f"Nem ismert kategória: '{kategoria}'",
                "elerheto_kategoriak": sorted(data.keys()),
                "javaslat": "Használd a list_kepviseloi_keretek tool-t a teljes listáért.",
            }

        return {
            "talalat": True,
            "kategoria": key,
            "kozelito_figyelmeztetes": _kozelito_figyelmeztetes(data),
            **data[key],
        }

    @mcp.tool
    def list_kepviseloi_keretek() -> dict:
        """
        Listázza az összes képviselői és frakciós keret-kategóriát,
        csoportosítva (egyéni / frakciós / szankció / alap).
        """
        data = _load_keretek()
        keys = set(data.keys())

        def _pick(keep):
            return [k for k in keep if k in keys]

        return {
            "alap": _pick(["alap_szamok", "tiszteletdij", "gazdalkodas"]),
            "egyeni_keretek": _pick(_EGYENI_KULCSOK),
            "frakcio_keretek": _pick(_FRAKCIO_KULCSOK),
            "puha_keretek": _pick(_PUHA_KULCSOK),
            "szankciok_tilalmak": _pick(_SZANKCIO_KULCSOK),
            "figyelmeztetes": _kozelito_figyelmeztetes(data),
        }

    @mcp.tool
    def szamol_tiszteletdij(tisztseg: str = "sima_kepviselo") -> dict:
        """
        Havi bruttó tiszteletdíjat ad meg tisztség szerint.

        Args:
            tisztseg: "sima_kepviselo" | "bizottsagi_tag" |
                "tab_tag_vagy_kettos" | "bizottsagi_alelnok" |
                "frakciovezeto_helyettes" (= jegyző / biz. elnök) |
                "frakciovezeto" (= OGY alelnök / háznagy) | "ogy_elnoke"

        Returns:
            dict: szorzó, havi bruttó forint, jogforras, megjegyzés
        """
        data = _load_keretek()
        td = data.get("tiszteletdij", {})
        tisztsegek = td.get("tisztsegek", {})
        key = tisztseg.lower().strip()

        if key not in tisztsegek:
            return {
                "talalat": False,
                "hiba": f"Nem ismert tisztség: '{tisztseg}'",
                "elerheto_tisztsegek": list(tisztsegek.keys()),
            }

        entry = tisztsegek[key]
        return {
            "talalat": True,
            "tisztseg": key,
            **entry,
            "alap_T_ft": td.get("alap_ft"),
            "jogforras": td.get("jogforras"),
            "kozelito_figyelmeztetes": _kozelito_figyelmeztetes(data),
        }

    @mcp.tool
    def szamol_frakcio_keret(
        letszam: int,
        kozos_listas: bool = False,
    ) -> dict:
        """
        Egy adott létszámú frakció havi működési keretét számolja ki.

        Képlet:
            alapkeret (T × 10) vagy közös listás (T × 17)
            + létszám × T × 0,5  (tagonkénti fejkvóta)
            + bérkeret = segítőlétszám × KSH × 4

        A segítőlétszám = alapsáv (115. § (2) a) + létszám (115. § (2) b)

        Args:
            letszam: A frakció képviselőinek száma.
            kozos_listas: True, ha közös országos listán mandátumot szerzett
                frakcióról van szó (alapkeret T × 17, mandátumarányosan osztva).

        Returns:
            dict: részletes bontás (alapkeret, fejkvóta, segítőlétszám,
                  bérkeret, cafetéria/jutalom), havi összeg, jogforras.
        """
        data = _load_keretek()
        alap = data.get("alap_szamok", {})
        T = alap.get("tiszteletdij_alap_T_ft", 2182488)
        ksh = alap.get("ksh_bruttó_atlagkereset_2025_ft", 727496)

        if letszam < 1:
            return {"talalat": False, "hiba": "Létszámnak legalább 1-nek kell lennie."}

        # Alapkeret
        if kozos_listas:
            alapkeret_ft = T * 17
            alapkeret_nev = "Közös listás frakció alapkeret (T × 17, mandátumarányosan osztva)"
        else:
            alapkeret_ft = T * 10
            alapkeret_nev = "Frakció alapkeret (T × 10)"

        # Fejkvóta (113. § (1) b)
        fejkvota_per_fo = T // 2
        fejkvota_ossz = fejkvota_per_fo * letszam

        # 114. § (3) dologi / irodafenntartási keret (T × 0,8 / fő)
        dologi_per_fo = int(T * 0.8)
        dologi_ossz = dologi_per_fo * letszam

        # Segítőlétszám-sávok (115. § (2) a)
        def _sav(l: int) -> int:
            if l <= 10:
                return 10
            if l <= 20:
                return 14
            if l <= 34:
                return 20
            if l <= 50:
                return 24
            if l <= 70:
                return 30
            if l <= 90:
                return 40
            if l <= 110:
                return 50
            if l <= 120:
                return 60
            return 80

        alapsav = _sav(letszam)
        # 115. § (2) b) — PLUSZ az OGY Hivatala által foglalkoztatott,
        # a frakció létszámával megegyező számú közép- vagy felsőfokú
        # végzettségű munkatárs. NEM frakció-tag; a MUNKÁLTATÓ az OGYH.
        plusz_ogyh_fo = letszam
        segitolet = alapsav + plusz_ogyh_fo

        # Bérkeret
        per_fo_berkeret = ksh * 4
        berkeret_ossz = per_fo_berkeret * segitolet

        # Jutalom (bérkeret 10%)
        jutalom = int(berkeret_ossz * 0.10)

        havi_mukodesi_ossz = alapkeret_ft + fejkvota_ossz + dologi_ossz

        return {
            "talalat": True,
            "letszam": letszam,
            "kozos_listas": kozos_listas,
            "T_alap_ft": T,
            "ksh_ft": ksh,
            "alapkeret": {
                "nev": alapkeret_nev,
                "havi_ft": alapkeret_ft,
                "jogforras": "Ogytv. 113. § (1) a)",
            },
            "fejkvota": {
                "per_fo_havi_ft": fejkvota_per_fo,
                "ossz_havi_ft": fejkvota_ossz,
                "jogforras": "Ogytv. 113. § (1) b)",
            },
            "dologi_keret_114_3": {
                "per_fo_havi_ft": dologi_per_fo,
                "ossz_havi_ft": dologi_ossz,
                "szorzo_T": 0.8,
                "jogforras": "Ogytv. 114. § (3)",
                "leiras": "Irodafenntartási / dologi keret (T × 80% / fő) — OGY-épületeken kívüli iroda berendezésére, felszerelésére és üzemeltetésére.",
            },
            "havi_mukodesi_keret_ft": havi_mukodesi_ossz,
            "segitoszemelyzet": {
                "alapsav_fo": alapsav,
                "alapsav_jogforras": "Ogytv. 115. § (2) a) — sávos létszám frakcióméret szerint",
                "plusz_ogy_hivatali_munkatars_fo": plusz_ogyh_fo,
                "plusz_megjegyzes": (
                    "PLUSZ a frakció létszámával megegyező számú, OGY HIVATALA "
                    "által (nem a frakció által!) foglalkoztatott közép- vagy "
                    "felsőfokú végzettségű munkatárs. NEM frakció-tag — a "
                    "frakciólétszámon FELÜL jön."
                ),
                "plusz_jogforras": "Ogytv. 115. § (2) b)",
                "ossz_ogyh_alkalmazott_fo": segitolet,
            },
            "berkeret": {
                "per_fo_havi_ft": per_fo_berkeret,
                "ossz_havi_ft": berkeret_ossz,
                "keplet": "segítőlétszám × KSH × 4",
                "jogforras": "Ogytv. 115. § (4)",
            },
            "jutalom_havi_ft": jutalom,
            "jutalom_megjegyzes": "Bérkeret 10%-a; új foglalkoztatás ebből NEM finanszírozható (115. § (6)).",
            "teljes_havi_keret_ft": havi_mukodesi_ossz + berkeret_ossz + jutalom,
            "teljes_bontas": "alapkeret + fejkvóta + dologi (114. § (3)) + bérkeret + jutalom",
            "jogforras": "Ogytv. 113–115. §",
            "kozelito_figyelmeztetes": _kozelito_figyelmeztetes(data),
        }

    @mcp.tool
    def szamol_uzemanyag_km(
        tavolsag_bp: str,
        egyeni_vk: bool = False,
        vk_terulet_km2: Optional[float] = None,
    ) -> dict:
        """
        Havi üzemanyag km-keretet számol lakóhely-távolság és VK-terület szerint.

        Args:
            tavolsag_bp: "budapesten_belul" | "1_100_km" | "101_200_km"
                       | "201_300_km" | "300_km_folott"
            egyeni_vk: Egyéni választókerületi képviselő-e.
            vk_terulet_km2: A választókerület területe km²-ben (ha egyeni_vk).

        Returns:
            dict: alap km, emelés %, végső km/hó, jogforras.
        """
        km_tabla = {
            "budapesten_belul": 2500,
            "1_100_km": 4000,
            "101_200_km": 5000,
            "201_300_km": 6000,
            "300_km_folott": 6500,
        }
        t = tavolsag_bp.lower().strip()
        if t not in km_tabla:
            return {
                "talalat": False,
                "hiba": f"Ismeretlen távolság-kategória: '{tavolsag_bp}'",
                "elerheto": list(km_tabla.keys()),
            }
        alap_km = km_tabla[t]
        emeles_pct = 0
        if egyeni_vk and vk_terulet_km2 is not None:
            if vk_terulet_km2 < 850:
                emeles_pct = 10
            elif vk_terulet_km2 < 1151:
                emeles_pct = 20
            elif vk_terulet_km2 < 1401:
                emeles_pct = 30
            elif vk_terulet_km2 < 1651:
                emeles_pct = 40
            elif vk_terulet_km2 < 1901:
                emeles_pct = 50
            else:
                emeles_pct = 60
        vegso_km = int(alap_km * (1 + emeles_pct / 100))
        return {
            "talalat": True,
            "tavolsag_kategoria": t,
            "alap_km": alap_km,
            "egyeni_vk": egyeni_vk,
            "vk_terulet_km2": vk_terulet_km2,
            "emeles_pct": emeles_pct,
            "havi_km_keret": vegso_km,
            "megjegyzes": (
                "A forintösszeg NAV üzemanyagára × 2000 cm³ benzines norma × km. "
                "Felhasználható üzemanyagra, útdíjra, karbantartásra, el. töltésre, "
                "sőt belföldi közösségi közlekedésre is (109. § (7))."
            ),
            "jogforras": "Ogytv. 109. §",
        }
