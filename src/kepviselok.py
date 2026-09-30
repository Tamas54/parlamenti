"""
Képviselők, frakciók, bizottsági tagságok — a parlament.hu „felicitas” API-jából.
==================================================================================
A parlament.hu bizottsági oldala a ciklus MEGSZŰNT tagságait is listázza
(kilépett tagok, szerepváltások duplán), ezért a jelenlegi állapotot
személyenként, a tagság vége-dátumából rakjuk össze.

Futtatás:
  python src/kepviselok.py            → friss lekérés + snapshot írása
Szerver: get_data() — memóriában tartja, háttérben frissít (REFRESH_SEC).
"""

import base64
import gzip
import json
import logging
import re
import threading
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("parlamentaris-mcp.kepviselok")

API = "https://www.parlament.hu/felicitas/api"
KEPV_Q = API + "/query/select/registry/kepviselo-query-provider/"
BIZ_Q = API + "/query/select/bizottsagadatok-bizottsag-registry/bizottsag-query-provider/"
RES = API + "/query/resource/kepviseloexportok/kepviselo-exported-queries-provider/"
LISTA_URL = "https://www.parlament.hu/aktiv-kepviselok-listaja"

SNAPSHOT = Path(__file__).resolve().parent / "data" / "kepviselok.json"
REFRESH_SEC = 6 * 3600
WORKERS = 6
UA = "Mozilla/5.0 (compatible; ParlamentarisKompendium/0.3; +https://parlamenti-production.up.railway.app)"

# Ellenőrző kapu: ennél kevesebb képviselő / bizottság = hiányos lekérés, nem írjuk felül a régit
MIN_KEPVISELO = 150
MIN_BIZOTTSAG = 10


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def _post(url: str, body: dict, retries: int = 3) -> dict:
    data = json.dumps(body).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": UA})
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.load(r)
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(1.5 * (attempt + 1))


def _rows(resp: dict) -> list[dict]:
    names = [f["name"] for f in resp["metadata"]["fields"]]
    return [dict(zip(names, row)) for row in resp["rows"]]


def _select(url: str, body: dict) -> list[dict]:
    """Lapozó lekérés: a felicitas 25-ös lapokat ad, ha nem kér mindent (-1)."""
    out, page = [], 0
    while True:
        resp = _post(f"{url}?page={page}", body)
        out += _rows(resp)
        if resp["response"].get("pageSize", -1) < 0 or not resp["rows"] or len(out) >= resp["response"]["totalSize"]:
            return out
        page += 1


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def _page_link(page: str, obj_id: str) -> str:
    """parlament.hu mélylink (a felicitas tömörített #page= paramétere)."""
    raw = json.dumps({"page": page, "hydration": {"open": {"id": obj_id}}}, separators=(",", ":")).encode()
    enc = base64.urlsafe_b64encode(gzip.compress(raw, mtime=0)).decode().rstrip("=")
    return f"{LISTA_URL}#page=cv1gzb-{enc}"


def _mp_url(pid: str) -> str:
    return _page_link("kepviseloexportok/kepviselo-adatlap-with-contract/kepviselo-adatlap-with-contract", pid)


def _biz_url(bid: str) -> str:
    return _page_link("bizottsagexportok/exported-bizottsag-adatlap/exported-bizottsag-adatlap", bid)


def _slug(s: str) -> str:
    tr = str.maketrans("áéíóöőúüűÁÉÍÓÖŐÚÜŰ", "aeiooouuuAEIOOOUUU")
    return re.sub(r"[^a-z0-9]+", "-", s.translate(tr).lower()).strip("-")


def _date(s):
    return s[:10] if s else None


# ---------------------------------------------------------------------------
# LEKÉRÉS
# ---------------------------------------------------------------------------

def fetch_all() -> dict:
    t0 = time.time()
    lista = _select(KEPV_Q + "aktiv-kepviselo-lista-query", {"pAktivKepviselo": True})
    aktiv_ids = {m["id"] for m in lista}

    def szemely(pid: str, kepviselo: bool) -> dict:
        body = {"pId": pid}
        r = {
            "adat": _select(KEPV_Q + "kepviselo-adatok-query_v2", body),
            "biz": _select(KEPV_Q + "kepviselo-bizottsagi-tagsagai-query_v2", body),
        }
        if kepviselo:
            r["valaszt"] = _select(KEPV_Q + "kepviselo-valasztasi-adatok-query_v2", body)
        else:
            r["szoszolo"] = _select(KEPV_Q + "szoszolo-mandatum-adatok-query_v2", body)
        return r

    with ThreadPoolExecutor(WORKERS) as ex:
        mp_raw = dict(zip([m["id"] for m in lista], ex.map(lambda m: szemely(m["id"], True), lista)))

    # Aktuális ciklus = az aktív képviselők folyó mandátumának ciklusa
    ciklus = Counter(v["cikus"] for r in mp_raw.values() for v in r["valaszt"] if not v["mandatumVege"]).most_common(1)[0][0]
    ciklus_ev = ciklus[:4]

    # Bizottsági névsorok (tartalmazzák a megszűnt tagságokat is) → csak a nem-képviselő
    # személyek felderítésére (nemzetiségi szószólók, volt képviselők) és a kormánypárti jelzőre
    biz_lista = _select(BIZ_Q + "bizottsag-tagjai-query", {})
    folyo_biz = [b for b in biz_lista if not b["megszuntetesDatuma"] and (b["letrehozasDatuma"] or "") >= ciklus_ev]
    kormanyparti, egyeb_ids = {}, set()
    for b in folyo_biz:
        for row in (b.get("bizottsagiTagok") or {}).get("rows", []):
            pid, _nev, _szerep, fid, _fnev, _eros, korm = row
            if fid is not None and korm is not None:
                kormanyparti[fid] = bool(korm)
            if pid not in aktiv_ids:
                egyeb_ids.add(pid)

    with ThreadPoolExecutor(WORKERS) as ex:
        egyeb_raw = dict(zip(sorted(egyeb_ids), ex.map(lambda p: szemely(p, False), sorted(egyeb_ids))))

    # Bizottságok adatlapja (típus, kód, elérhetőség) — minden, a ciklusban előforduló tagság alapján
    biz_ids = {b["bizottsagId"] for r in list(mp_raw.values()) + list(egyeb_raw.values())
               for b in r["biz"] if b["ciklus"] == ciklus}
    with ThreadPoolExecutor(WORKERS) as ex:
        mini = dict(zip(sorted(biz_ids), ex.map(lambda b: (_select(BIZ_Q + "bizottsag-mini-adatlap-query", {"pId": b}) or [None])[0], sorted(biz_ids))))
    fo_ids = [b for b, m in mini.items() if m and m["nemAlbizottsag"] and not m["megszuntetesDatuma"]]
    with ThreadPoolExecutor(WORKERS) as ex:
        alb = ex.map(lambda b: _select(BIZ_Q + "albizottsagok-query", {"pId": b}), fo_ids)
    fobiz = {a["alBizottsagId"]: a["fobizottsagId"] for rows in alb for a in rows}

    frakcio_ids = sorted({m["frakcioId"] for m in lista})
    szinek = {}
    for fid in frakcio_ids:
        try:
            m = re.search(r'fill="(#[0-9A-Fa-f]{3,8})"', _get_text(RES + f"kepviselo-magasabb-csik-svg-query/{fid}"))
            szinek[fid] = m.group(1) if m else None
        except Exception:
            szinek[fid] = None

    data = build(lista, mp_raw, egyeb_raw, mini, fobiz, szinek, kormanyparti, ciklus)
    log.info("kepviselok: %d képviselő, %d bizottság, %d szószóló — %.1f s",
             len(data["kepviselok"]), len(data["bizottsagok"]), len(data["szoszolok"]), time.time() - t0)
    return data


# ---------------------------------------------------------------------------
# ÖSSZERAKÁS (tiszta függvény)
# ---------------------------------------------------------------------------

SZEREP_REND = {"elnök": 0, "alelnök": 1, "tag": 2}


def build(lista, mp_raw, egyeb_raw, mini, fobiz, szinek, kormanyparti, ciklus) -> dict:
    nevek = {m["id"]: m["nev"] for m in lista}
    for pid, r in egyeb_raw.items():
        if r["adat"]:
            nevek[pid] = r["adat"][0]["nev"]

    bizottsagok = {}
    for bid, m in mini.items():
        if not m or m["megszuntetesDatuma"]:
            continue
        nev = re.sub(r"\s+", " ", m["bizottsagNev"]).strip()
        bizottsagok[bid] = {
            "id": bid,
            "nev": nev,
            "slug": _slug(nev),
            "kod": m["bizottsagAllandoKod"],
            "tipus": m["bizottsagTipus"] or ("albizottság" if not m["nemAlbizottsag"] else None),
            "albizottsag": not m["nemAlbizottsag"],
            "fobizottsag_id": fobiz.get(bid),
            "letrehozva": _date(m["letrahozasDatuma"]),
            "email": (m["emailCim"] or "").replace("[kukac]", "@") or None,
            "url": _biz_url(bid),
            "tagok": [],
            "korabbi_tagok": [],
        }
    # Albizottság slugja a főbizottságéval együtt egyedi (sok „Ellenőrző Albizottság” van)
    for b in bizottsagok.values():
        fo = bizottsagok.get(b["fobizottsag_id"])
        if fo:
            b["slug"] = f'{fo["slug"]}--{b["slug"]}'
            b["fobizottsag_nev"] = fo["nev"]

    def tagsagok(pid, r):
        folyo = []
        for t in r["biz"]:
            if t["ciklus"] != ciklus or t["bizottsagId"] not in bizottsagok:
                continue
            biz = bizottsagok[t["bizottsagId"]]
            rec = {"id": pid, "szerep": t["bizottsagiTisztseg"], "kezdet": _date(t["tisztsegKezdete"]), "vege": _date(t["tisztsegVege"])}
            if t["tisztsegVege"]:
                biz["korabbi_tagok"].append(rec)
            else:
                biz["tagok"].append({"id": pid, "szerep": rec["szerep"], "kezdet": rec["kezdet"]})
                folyo.append({"id": biz["id"], "szerep": rec["szerep"], "kezdet": rec["kezdet"]})
        return folyo

    kepviselok = []
    for m in lista:
        r = mp_raw[m["id"]]
        a = r["adat"][0] if r["adat"] else {}
        vk = next((v["valasztasiKerulet"] for v in r["valaszt"] if v["cikus"] == ciklus and not v["mandatumVege"]), None)
        kepviselok.append({
            "id": m["id"],
            "nev": m["nev"],
            "rendezo_nev": m["nevElonevNelkul"] or m["nev"],
            "frakcio_id": m["frakcioId"],
            "frakcio": m["frakcioNev"],
            "frakcio_tisztseg": None if m["frakcioTisztseg"] == "tag" else m["frakcioTisztseg"],
            "ogy_tisztseg": a.get("orszaggyulesiTisztseg"),
            "allami_tisztseg": a.get("allamiTisztseg"),
            "valasztokerulet": vk,
            "ulohely": m["ulohely"],
            "email": a.get("emailCim"),
            "url": _mp_url(m["id"]),
            "bizottsagok": tagsagok(m["id"], r),
        })

    szoszolok = []
    for pid, r in egyeb_raw.items():
        folyo_mandatum = next((s for s in r.get("szoszolo", []) if s["ciklus"] == ciklus and not s["mandatumVege"]), None)
        if folyo_mandatum:
            a = r["adat"][0] if r["adat"] else {}
            szoszolok.append({
                "id": pid,
                "nev": nevek.get(pid, pid),
                "nemzetiseg": folyo_mandatum["nemzetiseg"],
                "email": a.get("emailCim"),
                "url": _mp_url(pid),
                "bizottsagok": tagsagok(pid, r),
            })
        else:
            tagsagok(pid, {"biz": [t for t in r["biz"] if t["tisztsegVege"]]})  # volt képviselő: csak megszűnt tagság

    jelenlegi = {m["id"] for m in lista} | {s["id"] for s in szoszolok}
    for b in bizottsagok.values():
        b["tagok"].sort(key=lambda t: (SZEREP_REND.get(t["szerep"], 9), nevek.get(t["id"], "")))
        # szerepváltás (pl. elnök → tag) nem „korábbi tag”, ha ugyanaz a személy most is tag
        most = {t["id"] for t in b["tagok"]}
        b["korabbi_tagok"] = sorted(
            [dict(t, nev=nevek.get(t["id"], t["id"]), mar_nem_kepviselo=t["id"] not in jelenlegi)
             for t in b["korabbi_tagok"] if t["id"] not in most],
            key=lambda t: t["vege"] or "")

    letszam = Counter(m["frakcio_id"] for m in kepviselok)
    frakciok = []
    for fid, n in letszam.most_common():
        nev = next(m["frakcio"] for m in kepviselok if m["frakcio_id"] == fid)
        frakciok.append({"id": fid, "nev": nev, "szin": szinek.get(fid), "letszam": n, "kormanyparti": kormanyparti.get(fid)})

    return {
        "frissitve": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "forras": LISTA_URL,
        "ciklus": ciklus,
        "kep_url": RES + "kepviselo-kepek/{id}",
        "frakciok": frakciok,
        "kepviselok": kepviselok,
        "szoszolok": sorted(szoszolok, key=lambda s: s["nemzetiseg"] or ""),
        "bizottsagok": list(bizottsagok.values()),
    }


def check(data: dict) -> None:
    """Ellenőrző kapu: hiányos lekérés ne írja felül a jó adatot."""
    n_mp, n_biz = len(data["kepviselok"]), len([b for b in data["bizottsagok"] if b["tagok"]])
    if n_mp < MIN_KEPVISELO or n_biz < MIN_BIZOTTSAG:
        raise ValueError(f"hiányos lekérés: {n_mp} képviselő, {n_biz} bizottság taggal")
    ures = [m["nev"] for m in data["kepviselok"] if not m["valasztokerulet"]]
    if len(ures) > n_mp // 10:
        raise ValueError(f"{len(ures)} képviselőnél hiányzik a választókerület")


# ---------------------------------------------------------------------------
# CACHE (szerver)
# ---------------------------------------------------------------------------

_lock = threading.Lock()
_state = {"data": None, "loaded_at": 0.0, "refreshing": False, "last_error": None, "last_attempt": None}


def _load_snapshot():
    try:
        with open(SNAPSHOT, encoding="utf-8") as f:
            _state["data"] = json.load(f)
        ts = datetime.fromisoformat(_state["data"]["frissitve"]).timestamp()
        _state["loaded_at"] = ts
    except Exception as e:
        log.warning("kepviselok snapshot nem olvasható: %s", e)


def _refresh():
    _state["last_attempt"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        data = fetch_all()
        check(data)
        with _lock:
            _state["data"], _state["loaded_at"], _state["last_error"] = data, time.time(), None
    except Exception as e:
        _state["last_error"] = f"{type(e).__name__}: {e}"
        log.exception("kepviselok frissítés sikertelen — marad a korábbi adat")
    finally:
        _state["refreshing"] = False


def ensure_fresh():
    """Háttérfrissítés indítása, ha az adat régebbi REFRESH_SEC-nél (nem blokkol)."""
    with _lock:
        if _state["data"] is None and not _state["loaded_at"]:
            _load_snapshot()
        stale = time.time() - _state["loaded_at"] > REFRESH_SEC
        if stale and not _state["refreshing"]:
            _state["refreshing"] = True
            threading.Thread(target=_refresh, daemon=True, name="kepviselok-refresh").start()


def get_data() -> dict | None:
    ensure_fresh()
    d = _state["data"]
    if d is None:
        return None
    return dict(d, frissites={"folyamatban": _state["refreshing"], "utolso_hiba": _state["last_error"], "utolso_probalkozas": _state["last_attempt"]})


def start_background_loop():
    def loop():
        while True:
            ensure_fresh()
            time.sleep(600)
    threading.Thread(target=loop, daemon=True, name="kepviselok-loop").start()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    d = fetch_all()
    check(d)
    SNAPSHOT.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"snapshot: {SNAPSHOT} — {len(d['kepviselok'])} képviselő, {len(d['bizottsagok'])} bizottság, {len(d['szoszolok'])} szószóló")
