"""
Ki mivel foglalkozott — képviselői tevékenység a parlament.hu „felicitas” API-jából.

A ciklus TELJES listái (kulcs nélkül, nyilvános):
  * felszólalások — `egy-kepviselo-felszolalasai-query` paraméter nélkül az összeset
    adja egy hívásban (2026-10-05: 6328 sor, ~6 s): napirendi pont, a tárgyalt önálló
    indítvány(ok), szerep (felszólalás, kérdés, vezérszónoklat…), időtartam;
  * önálló indítványok — `iromany-esemeny-benyujto-szerint-query` (25-ös lapok):
    szám, cím, főtípus, állapot, MINDEN benyújtó;
  * módosító javaslatok — `nem-onallo-iromany-lista-query`: melyik törvényjavaslatot
    módosítja, ki nyújtotta be.
Ebből személyenkénti index és téma-összesítő („ki mivel foglalkozott”). A felszólalások
SZÖVEGÉBEN a keresés élőben megy (`pFelszSzoveg`, ~0,2 s) — azt nem tároljuk.

Frissítés 6 óránként háttérben; ellenőrző kapu + `data/tevekenyseg.json` snapshot-tartalék
(ugyanaz a minta, mint a `kepviselok.py`-ban).
"""

import json
import logging
import re
import threading
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import kepviselok
from kepviselok import API, KEPV_Q, _page_link, _post, _rows, _select

log = logging.getLogger("tevekenyseg")

FELSZ_Q = API + "/query/select/plenarisulesadatok-plenarisules-registry/plenaris-ules-adatok-query-provider/egy-kepviselo-felszolalasai-query"
ONALLO_Q = API + "/query/select/iromanyadatok-iromany-registry/iromanyok-query-provider/iromany-esemeny-benyujto-szerint-query"
MODOSITO_Q = API + "/query/select/iromanyexportok-registry/iromany-adatlap-query-provider/nem-onallo-iromany-lista-query"

SNAPSHOT = Path(__file__).resolve().parent / "data" / "tevekenyseg.json"
REFRESH_SEC = 6 * 3600
# Ellenőrző kapu: a friss lekérés nem lehet a régi snapshot felénél kisebb (hiányos lekérés)
MIN_ARANY = 0.5

#: a napirendi pont FORMÁJA (nem témája) — ezek a műfaj-statisztikába mennek, nem a témák közé
_MUFAJ_MINTAK = ("napirend előtti", "napirend utáni", "kérdés", "azonnali", "interpelláció",
                 "ülésnap megnyitása", "ülésnap bezárása", "határozati házszabályi", "bejelentés",
                 "eskü", "személyes érintettség", "ügyrendi", "napirend elfogadása", "napirendi javaslat")


# ---------------------------------------------------------------------------
# SEGÉDEK
# ---------------------------------------------------------------------------

def norm(s) -> str:
    """Ékezet- és kisbetű-független alak a kereséshez."""
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def _szavak(q: str) -> list[str]:
    return [w for w in re.split(r"\s+", norm(q).strip()) if w]


def _talal(szoveg: str, szavak: list[str]) -> bool:
    t = norm(szoveg)
    return bool(szavak) and all(w in t for w in szavak)


def _beagyazott(mezo) -> list[list]:
    return (mezo or {}).get("rows") or []


def _datum(s) -> str | None:
    return s[:10] if s else None


def _iromany_url(iid: str) -> str:
    return _page_link("iromanyexportok/iromany-adatlap-with-contract/iromany-adatlap-with-contract", iid)


def _felszolalas_url(fid: str) -> str:
    return _page_link("plenarisulesexportok/ulesnap-felszolalas-adata-with-contract/ulesnap-felszolalas-adata-with-contract", fid)


def _mufaj(napirend: str) -> bool:
    n = norm(napirend)
    return any(norm(m) in n for m in _MUFAJ_MINTAK)


# ---------------------------------------------------------------------------
# LEKÉRÉS
# ---------------------------------------------------------------------------

def _ciklus_id(kv: dict | None) -> int:
    """A folyó ciklus numerikus azonosítója (a felszólalás-szám lekérdezés adja)."""
    mps = (kv or {}).get("kepviselok") or []
    for m in mps[:5]:
        try:
            rows = _select(KEPV_Q + "kepviselo-felszolalasok-szama-query_v2", {"pId": m["id"]})
            if rows and rows[0].get("ciklusId"):
                return int(rows[0]["ciklusId"])
        except Exception as e:  # noqa: BLE001
            log.warning("ciklus-azonosító lekérés hiba (%s): %s", m.get("id"), e)
    raise RuntimeError("a ciklus azonosítója nem kérhető le")


def fetch_all(kv: dict | None = None) -> dict:
    t0 = time.time()
    kv = kv or kepviselok.get_data()
    c = _ciklus_id(kv)
    felsz = _rows(_post(FELSZ_Q + "?page=0", {"pMultiCiklus": [c]}))   # pageSize -1: egy hívás
    onallo = _select(ONALLO_Q, {"pMultiCiklus": [c]})
    modosito = _select(MODOSITO_Q, {"pCiklus": [c]})
    data = build(felsz, onallo, modosito, kv, c)
    log.info("tevekenyseg: %d felszólalás, %d önálló indítvány, %d módosító, %d személy — %.1f s",
             len(felsz), len(onallo), len(modosito), len(data["szemelyek"]), time.time() - t0)
    return data


# ---------------------------------------------------------------------------
# ÖSSZERAKÁS (tiszta függvény)
# ---------------------------------------------------------------------------

def build(felsz: list[dict], onallo: list[dict], modosito: list[dict], kv: dict | None, ciklus_id: int) -> dict:
    nevek = {m["id"]: m["nev"] for m in ((kv or {}).get("kepviselok") or []) + ((kv or {}).get("szoszolok") or [])}
    sz: dict[str, dict] = defaultdict(lambda: {"felszolalasok": [], "inditvanyok": [], "modositok": []})

    for f in felsz:
        pid = f.get("kepviseloId")
        if not pid:
            continue
        nevek.setdefault(pid, f.get("kepviseloNev") or pid)
        sz[pid]["felszolalasok"].append({
            "id": f.get("felszolalasId"),
            "datum": _datum(f.get("ulesnapKezdete")),
            "ido_s": f.get("felszolalasiIdo") or 0,
            "napirend": [r[0] for r in _beagyazott(f.get("napirendiPontok")) if r and r[0]],
            "inditvany": [{"id": r[0], "cim": r[1]} for r in _beagyazott(f.get("onalloInditvanyok")) if len(r) > 1],
            "szerep": [r[0] for r in _beagyazott(f.get("szerepek")) if r and r[0]],
            "url": _felszolalas_url(f["felszolalasId"]) if f.get("felszolalasId") else None,
        })

    for i in onallo:
        benyujtok = [r for r in _beagyazott(i.get("benyujto")) if len(r) > 1 and r[1]]
        tetel = {
            "id": i.get("iromanyId"), "szam": i.get("iromanyNev"), "cim": i.get("iromanyCime") or "",
            "fotipus": i.get("iromanyFotipus"), "datum": _datum(i.get("benyujtasDatuma")),
            "allapot": i.get("allapot"), "benyujtok": len(benyujtok),
            "url": _iromany_url(i["iromanyId"]) if i.get("iromanyId") else None,
        }
        for r in benyujtok:
            nevek.setdefault(r[1], re.sub(r"\s*\([^)]*\)\s*$", "", r[-1] or "") or r[1])
            sz[r[1]]["inditvanyok"].append(tetel)

    for m in modosito:
        alap = (_beagyazott(m.get("onalloIromany")) or [[None, "", ""]])[0]
        tetel = {
            "id": m.get("modositoId"), "szam": m.get("iromanyszam"), "tipus": m.get("tipus"),
            "datum": _datum(m.get("benyujtasDatuma")),
            "alap": {"id": alap[0], "cim": alap[1] if len(alap) > 1 else "", "szam": alap[2] if len(alap) > 2 else ""},
            "url": _iromany_url(alap[0]) if alap[0] else None,
        }
        for r in _beagyazott(m.get("benyujto")):
            if len(r) > 1 and r[1]:                       # [id, kepviseloId, frakcioId, bizottsagId, …, név]
                nevek.setdefault(r[1], re.sub(r"\s*\([^)]*\)\s*$", "", r[-1] or "") or r[1])
                sz[r[1]]["modositok"].append(tetel)

    szemelyek = {}
    for pid, d in sz.items():
        d["felszolalasok"].sort(key=lambda x: x["datum"] or "", reverse=True)
        d["inditvanyok"].sort(key=lambda x: x["datum"] or "", reverse=True)
        d["modositok"].sort(key=lambda x: x["datum"] or "", reverse=True)
        szemelyek[pid] = {"id": pid, "nev": nevek.get(pid, pid), **d,
                          "temak": temak(d), "stat": stat(d)}
    return {
        "frissitve": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "forras": "https://www.parlament.hu (felicitas API)",
        "ciklus_id": ciklus_id,
        "osszesen": {"felszolalas": len(felsz), "onallo_inditvany": len(onallo), "modosito": len(modosito)},
        "szemelyek": szemelyek,
    }


def temak(d: dict, n: int = 12) -> list[dict]:
    """A személy témái súlyozva: saját indítvány 3, módosító 2, felszólalás 1 (+ idő)."""
    t: dict[str, dict] = {}

    def add(kulcs, cim, suly, fajta, mp=0):
        if not cim:
            return
        e = t.setdefault(kulcs, {"cim": cim, "pont": 0.0, "inditvany": 0, "modosito": 0, "felszolalas": 0, "ido_s": 0})
        e["pont"] += suly + mp / 600.0
        e[fajta] += 1
        e["ido_s"] += mp

    for i in d["inditvanyok"]:
        add(i["id"] or i["cim"], f'{i["szam"]} {i["cim"]}'.strip(), 3, "inditvany")
    for m in d["modositok"]:
        a = m["alap"]
        add(a["id"] or a["cim"], f'{a["szam"]} {a["cim"]}'.strip(), 2, "modosito")
    for f in d["felszolalasok"]:
        if f["inditvany"]:
            for i in f["inditvany"]:
                add(i["id"], i["cim"], 1, "felszolalas", f["ido_s"])
        else:
            for nap in f["napirend"]:
                if not _mufaj(nap):
                    add("np:" + nap, nap, 1, "felszolalas", f["ido_s"])
    out = sorted(t.values(), key=lambda e: -e["pont"])[:n]
    for e in out:
        e["pont"] = round(e["pont"], 1)
    return out


def stat(d: dict) -> dict:
    mufaj = defaultdict(int)
    for f in d["felszolalasok"]:
        for s in f["szerep"] or ["felszólalás"]:
            mufaj[s] += 1
    return {"felszolalas": len(d["felszolalasok"]),
            "felszolalas_perc": round(sum(f["ido_s"] for f in d["felszolalasok"]) / 60),
            "onallo_inditvany": len(d["inditvanyok"]), "modosito": len(d["modositok"]),
            "mufaj": dict(sorted(mufaj.items(), key=lambda kv: -kv[1]))}


# ---------------------------------------------------------------------------
# KERESÉS (weben és MCP-n ugyanaz)
# ---------------------------------------------------------------------------

def szemely_keres(q: str, data: dict | None = None, limit: int = 10) -> list[dict]:
    """Név szerinti keresés (ékezet-független, részleges)."""
    data = data or get_data() or {}
    w = _szavak(q)
    return [s for s in data.get("szemelyek", {}).values() if _talal(s["nev"], w)][:limit]


def ki_foglalkozott(q: str, data: dict | None = None, limit: int = 20) -> list[dict]:
    """Téma szerinti keresés: kik foglalkoztak vele (indítvány, módosító, felszólalás), rangsorolva."""
    data = data or get_data() or {}
    w = _szavak(q)
    if not w:
        return []
    out = []
    for s in data.get("szemelyek", {}).values():
        ind = [i for i in s["inditvanyok"] if _talal(f'{i["szam"]} {i["cim"]} {i["fotipus"]}', w)]
        mod = [m for m in s["modositok"] if _talal(f'{m["alap"]["szam"]} {m["alap"]["cim"]}', w)]
        fel = [f for f in s["felszolalasok"]
               if _talal(" ".join([*f["napirend"], *(i["cim"] for i in f["inditvany"]), *f["szerep"]]), w)]
        if ind or mod or fel:
            pont = 3 * len(ind) + 2 * len(mod) + len(fel) + sum(f["ido_s"] for f in fel) / 600.0
            out.append({"id": s["id"], "nev": s["nev"], "pont": round(pont, 1),
                        "inditvanyok": ind[:5], "modositok": mod[:5], "felszolalasok": fel[:5],
                        "db": {"inditvany": len(ind), "modosito": len(mod), "felszolalas": len(fel)}})
    out.sort(key=lambda x: -x["pont"])
    return out[:limit]


def felszolalas_szoveg_kereses(szoveg: str, pid: str | None = None, limit: int = 30) -> dict:
    """ÉLŐ keresés a felszólalások SZÖVEGÉBEN (parlament.hu, `pFelszSzoveg`)."""
    data = get_data() or {}
    body = {"pFelszSzoveg": szoveg}
    if data.get("ciklus_id"):
        body["pMultiCiklus"] = [data["ciklus_id"]]
    if pid:
        body["pKepviselo"] = pid
    r = _post(FELSZ_Q + "?page=0", body)
    rows = _rows(r)
    talalat = [{"nev": f.get("kepviseloNev"), "id": f.get("kepviseloId"),
                "datum": _datum(f.get("ulesnapKezdete")),
                "napirend": [x[0] for x in _beagyazott(f.get("napirendiPontok")) if x and x[0]],
                "inditvany": [x[1] for x in _beagyazott(f.get("onalloInditvanyok")) if len(x) > 1],
                "szerep": [x[0] for x in _beagyazott(f.get("szerepek")) if x and x[0]],
                "ido_s": f.get("felszolalasiIdo") or 0,
                "url": _felszolalas_url(f["felszolalasId"]) if f.get("felszolalasId") else None}
               for f in rows]
    per_fo = defaultdict(int)
    for t in talalat:
        per_fo[t["nev"]] += 1
    return {"szoveg": szoveg, "osszes": r["response"].get("totalSize", len(talalat)),
            "kik": sorted(per_fo.items(), key=lambda kv: -kv[1]), "talalatok": talalat[:limit]}


def osszesito(data: dict | None = None) -> list[dict]:
    """Személyenként: számok + top témák (a web lista-nézetéhez, kicsi)."""
    data = data or get_data() or {}
    return [{"id": s["id"], "nev": s["nev"], "stat": s["stat"], "temak": s["temak"][:6]}
            for s in data.get("szemelyek", {}).values()]


# ---------------------------------------------------------------------------
# ELLENŐRZÉS + TÁROLÁS + FRISSÍTÉS (a kepviselok.py mintája)
# ---------------------------------------------------------------------------

_data: dict | None = None
_lock = threading.Lock()


def check(uj: dict, regi: dict | None) -> None:
    o = uj.get("osszesen") or {}
    if o.get("felszolalas", 0) <= 0 or len(uj.get("szemelyek") or {}) < 50:
        raise ValueError(f"hiányos lekérés: {o}, {len(uj.get('szemelyek') or {})} személy")
    if regi:
        for k in ("felszolalas", "onallo_inditvany", "modosito"):
            if o.get(k, 0) < MIN_ARANY * (regi.get("osszesen") or {}).get(k, 0):
                raise ValueError(f"a(z) {k} száma gyanúsan csökkent: {o.get(k)} < {MIN_ARANY} × {regi['osszesen'][k]}")


def _load_snapshot():
    try:
        with open(SNAPSHOT, encoding="utf-8") as f:
            return json.load(f)
    except Exception:  # noqa: BLE001
        return None


def _refresh():
    global _data
    regi = _data or _load_snapshot()
    uj = fetch_all()
    check(uj, regi)
    with _lock:
        _data = uj
    try:
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        tmp = SNAPSHOT.with_suffix(".tmp")
        tmp.write_text(json.dumps(uj, ensure_ascii=False), encoding="utf-8")
        tmp.replace(SNAPSHOT)
    except Exception as e:  # noqa: BLE001
        log.warning("tevekenyseg snapshot írás hiba: %s", e)


def get_data() -> dict | None:
    global _data
    if _data is None:
        with _lock:
            if _data is None:
                _data = _load_snapshot()
    return _data


def start_background_loop():
    def loop():
        time.sleep(30)          # a kepviselok első frissítése előbb fusson
        while True:
            try:
                _refresh()
            except Exception as e:  # noqa: BLE001
                log.warning("tevekenyseg frissítés hiba (a régi adat marad): %s", e)
            time.sleep(REFRESH_SEC)
    threading.Thread(target=loop, daemon=True, name="tevekenyseg").start()
