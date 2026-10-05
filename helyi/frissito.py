#!/usr/bin/env python3
"""
Helyi frissítő — a parlament.hu adatait ITTHONRÓL húzza le, és felküldi a szerverre.

Miért: a parlament.hu a Railway szerver IP-jére adat helyett CAPTCHA-lapot ad
(2026-10-05), ezért a szerver magától nem tud frissíteni. Itthonról (lakossági
IP) a nyilvános felicitas API rendesen válaszol. A CAPTCHA-t NEM kerüljük meg.

Futtatás:   python3 helyi/frissito.py           (systemd-időzítő 3 óránként)
Beállítás:  ~/.config/parlamenti/feltolto.env   PARL_FELTOLTO_KULCS=…  (600-as jog)
            PARL_URL=… (alap: https://parlamenti-production.up.railway.app)
Csak szabványos könyvtár. Kilépési kód: 0 = feltöltve, 1 = hiba.
"""
import gzip
import json
import logging
import os
import sys
import time
import urllib.request
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC))
BEALLITAS = Path.home() / ".config" / "parlamenti" / "feltolto.env"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("helyi-frissito")


def beallitas() -> dict:
    env = {}
    if BEALLITAS.exists():
        for sor in BEALLITAS.read_text(encoding="utf-8").splitlines():
            if "=" in sor and not sor.lstrip().startswith("#"):
                k, v = sor.split("=", 1)
                env[k.strip()] = v.strip()
    env.update({k: v for k, v in os.environ.items() if k.startswith("PARL_")})
    return env


def main() -> int:
    env = beallitas()
    kulcs = env.get("PARL_FELTOLTO_KULCS")
    url = env.get("PARL_URL", "https://parlamenti-production.up.railway.app").rstrip("/") + "/api/feltoltes"
    if not kulcs:
        log.error("nincs PARL_FELTOLTO_KULCS (%s)", BEALLITAS)
        return 1
    import kepviselok
    import tevekenyseg
    t0 = time.time()
    kv = kepviselok.fetch_all()
    kepviselok.check(kv)
    tev = tevekenyseg.fetch_all(kv)
    tevekenyseg.check(tev, None)
    torzs = gzip.compress(json.dumps({"kepviselok": kv, "tevekenyseg": tev}, ensure_ascii=False).encode())
    log.info("lehúzva %.0f s alatt: %d képviselő, %s — feltöltés %d KB",
             time.time() - t0, len(kv["kepviselok"]), tev["osszesen"], len(torzs) // 1024)
    req = urllib.request.Request(url, data=torzs, method="POST", headers={
        "Content-Type": "application/json", "Content-Encoding": "gzip", "X-Feltolto-Kulcs": kulcs})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            log.info("szerver: %s %s", r.status, r.read().decode()[:300])
            return 0
    except urllib.error.HTTPError as e:
        log.error("szerver elutasította: %s %s", e.code, e.read().decode()[:300])
    except Exception as e:  # noqa: BLE001
        log.error("feltöltés hiba: %s", e)
    return 1


if __name__ == "__main__":
    sys.exit(main())
