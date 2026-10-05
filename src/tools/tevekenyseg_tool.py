"""
Ki kicsoda + ki mivel foglalkozott — MCP-eszközök
=================================================
A parlament.hu „felicitas” API-jának adataiból (6 óránként frissítve, `kepviselok.py`,
`tevekenyseg.py`). A felszólalások SZÖVEGÉBEN a keresés élőben megy.

Eszközök:
  * kepviselo_adatok     — ki kicsoda: párt, választókerület, tisztségek, bizottságok
  * bizottsag_tagjai     — egy bizottság jelenlegi tagjai, tisztségekkel
  * kepviselo_tevekenyseg — egy képviselő mivel foglalkozott (témák, indítványok,
                            módosítók, felszólalások)
  * ki_foglalkozott      — egy témával kik foglalkoztak (rangsor)
  * felszolalas_kereses  — szabadszavas keresés a felszólalások szövegében

Minden adat forrása a parlament.hu; a válaszban a frissítés ideje és mélylinkek.
"""

from typing import Optional

from fastmcp import FastMCP

import kepviselok
import tevekenyseg as T


def _kv() -> dict:
    return kepviselok.get_data() or {}


def _forras(data: dict) -> dict:
    return {"forras": data.get("forras") or "https://www.parlament.hu", "frissitve": data.get("frissitve")}


def _szemelyek_nev_szerint(nev: str) -> list[dict]:
    kv = _kv()
    w = T._szavak(nev)
    mind = (kv.get("kepviselok") or []) + (kv.get("szoszolok") or [])
    return [m for m in mind if T._talal(m.get("nev"), w)]


def _biz_index(kv: dict) -> dict:
    return {b["id"]: b for b in kv.get("bizottsagok") or []}


def register_tevekenyseg_tools(mcp: FastMCP) -> None:

    @mcp.tool
    def kepviselo_adatok(nev: str) -> dict:
        """
        KI KICSODA: egy országgyűlési képviselő (vagy nemzetiségi szószóló) adatai —
        frakció, választókerület, országgyűlési / frakció- / állami tisztség,
        ülőhely, JELENLEGI bizottsági tagságok (szereppel), parlament.hu-adatlap link,
        és rövid tevékenység-összesítő (felszólalások, indítványok, fő témák).

        Args:
            nev: a képviselő neve vagy névrésze (ékezet nélkül is), pl. "Nacsa", "toroczkai"

        Returns:
            dict: {"talalatok": [...], "forras", "frissitve"} — több egyezésnél mindet adja
        """
        kv = _kv()
        biz = _biz_index(kv)
        tev = T.get_data() or {}
        out = []
        for m in _szemelyek_nev_szerint(nev)[:10]:
            s = (tev.get("szemelyek") or {}).get(m["id"]) or {}
            out.append({
                "nev": m.get("nev"), "id": m.get("id"), "frakcio": m.get("frakcio"),
                "valasztokerulet": m.get("valasztokerulet"),
                "tisztsegek": {k: m.get(k) for k in ("ogy_tisztseg", "frakcio_tisztseg", "allami_tisztseg") if m.get(k)},
                "ulohely": m.get("ulohely"), "email": m.get("email"), "adatlap": m.get("url"),
                "bizottsagok": [{"bizottsag": (biz.get(t["id"]) or {}).get("nev"), "szerep": t.get("szerep"),
                                 "kezdet": t.get("kezdet")} for t in m.get("bizottsagok") or []],
                "tevekenyseg": {"stat": s.get("stat"), "fo_temak": [e["cim"] for e in (s.get("temak") or [])[:5]]} if s else None,
            })
        return {"talalatok": out, **_forras(kv),
                "megjegyzes": None if out else "nincs ilyen nevű képviselő a jelenlegi ciklusban"}

    @mcp.tool
    def bizottsag_tagjai(bizottsag: str) -> dict:
        """
        Egy országgyűlési bizottság (vagy albizottság) JELENLEGI tagjai tisztséggel
        (elnök, alelnök, tag) és frakcióval.

        Args:
            bizottsag: a bizottság neve, névrésze vagy kódja, pl. "költségvetési", "MEB", "nemzetbiztonsági"

        Returns:
            dict: {"bizottsagok": [{"nev", "kod", "tipus", "tagok": [...]}], "forras", "frissitve"}
        """
        kv = _kv()
        mps = {m["id"]: m for m in (kv.get("kepviselok") or []) + (kv.get("szoszolok") or [])}
        w = T._szavak(bizottsag)
        out = []
        for b in kv.get("bizottsagok") or []:
            if not T._talal(f'{b.get("nev")} {b.get("kod")}', w):
                continue
            out.append({"nev": b.get("nev"), "kod": b.get("kod"), "tipus": b.get("tipus"),
                        "albizottsag": b.get("albizottsag"), "adatlap": b.get("url"),
                        "tagok": [{"nev": (mps.get(t["id"]) or {}).get("nev", t["id"]),
                                   "frakcio": (mps.get(t["id"]) or {}).get("frakcio"),
                                   "szerep": t.get("szerep")} for t in b.get("tagok") or []]})
        return {"bizottsagok": out[:8], **_forras(kv)}

    @mcp.tool
    def kepviselo_tevekenyseg(nev: str, reszletek: str = "temak", limit: int = 25) -> dict:
        """
        KI MIVEL FOGLALKOZOTT: egy képviselő parlamenti tevékenysége a folyó ciklusban.

        Args:
            nev: a képviselő neve vagy névrésze (ékezet nélkül is)
            reszletek: "temak" (alap: súlyozott témák + számok + műfajok),
                       "inditvanyok" (benyújtott önálló indítványai: törvényjavaslat,
                       határozati javaslat, kérdés, interpelláció…),
                       "modositok" (módosító javaslatai, melyik törvényhez),
                       "felszolalasok" (felszólalásai dátummal, napirendi ponttal,
                       a tárgyalt indítvánnyal, időtartammal, linkkel),
                       "mind"
            limit: listánként legfeljebb ennyi tétel (alap 25)

        Returns:
            dict: {"nev", "stat", "temak", [listák], "frissitve"}. A témák súlya:
            saját indítvány 3, módosító 2, felszólalás 1 (+ felszólalási idő).
        """
        tev = T.get_data() or {}
        talalat = T.szemely_keres(nev, tev, limit=5)
        if not talalat:
            return {"hiba": f"nincs tevékenységi adat erre a névre: {nev}", "frissitve": tev.get("frissitve")}
        out = []
        for s in talalat:
            e = {"nev": s["nev"], "id": s["id"], "stat": s["stat"], "temak": s["temak"]}
            for k in ("inditvanyok", "modositok", "felszolalasok"):
                if reszletek in (k, "mind"):
                    e[k] = s[k][:limit]
            out.append(e)
        return {"talalatok": out, "frissitve": tev.get("frissitve"), "forras": tev.get("forras")}

    @mcp.tool
    def ki_foglalkozott(tema: str, limit: int = 15) -> dict:
        """
        Egy TÉMÁVAL kik foglalkoztak a parlamentben: benyújtott indítvány (címben),
        módosító javaslat (a módosított javaslat címében), felszólalás (napirendi pont,
        tárgyalt indítvány címe, szerep). Rangsor: indítvány 3, módosító 2, felszólalás 1.

        A felszólalások SZÖVEGÉBEN keresni a `felszolalas_kereses` eszközzel lehet.

        Args:
            tema: kulcsszó(k), pl. "költségvetés", "szakképzés", "T/51", "vagyonvisszaszerzés"
            limit: legfeljebb ennyi képviselő (alap 15)

        Returns:
            dict: {"tema", "kepviselok": [{"nev", "pont", "db", példa-tételek}], "frissitve"}
        """
        tev = T.get_data() or {}
        return {"tema": tema, "kepviselok": T.ki_foglalkozott(tema, tev, limit=limit),
                "frissitve": tev.get("frissitve")}

    @mcp.tool
    def felszolalas_kereses(szoveg: str, kepviselo: Optional[str] = None, limit: int = 30) -> dict:
        """
        Szabadszavas keresés a parlamenti felszólalások SZÖVEGÉBEN (élőben a parlament.hu-n,
        a folyó ciklusban). Kiírja, ki hányszor és hol (dátum, napirendi pont, tárgyalt
        indítvány) mondta, linkkel a felszólalás adatlapjára.

        Args:
            szoveg: a keresett szó vagy kifejezés, pl. "devizahitel", "Paks II"
            kepviselo: opcionális névszűrő (csak ennek a képviselőnek a felszólalásai)
            limit: legfeljebb ennyi felszólalás a listában (alap 30)

        Returns:
            dict: {"szoveg", "osszes", "kik": [[név, db]], "talalatok": [...]}
        """
        pid = None
        if kepviselo:
            t = T.szemely_keres(kepviselo, limit=1)
            if not t:
                return {"hiba": f"nincs ilyen nevű képviselő: {kepviselo}"}
            pid = t[0]["id"]
        return T.felszolalas_szoveg_kereses(szoveg, pid=pid, limit=limit)
