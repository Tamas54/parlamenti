"""Parlament.hu kijáratok az Echolot echolot_proxy.py (d2b649b) mintájára.

Friss ingyenes lista, célhoz kötött próba, memo, hibánál hűtés és korlátos,
egyidejű felderítés. Csak TLS-ellenőrzött HTTPS cél, HTTP CONNECT proxyn.
Nincs globális urllib opener: a feltöltő hitelesítése nem kerül a készletbe.
"""
from __future__ import annotations

import json
import logging
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

log = logging.getLogger("parlamentaris-mcp.proxy")
UA = "Mozilla/5.0 (compatible; ParlamentarisKompendium/0.3; +https://parlamenti-production.up.railway.app)"
PROBE_URL = "https://www.parlament.hu/felicitas/api/query/select/registry/kepviselo-query-provider/aktiv-kepviselo-lista-query?page=0"


class UpstreamHiba(RuntimeError):
    """Nem elérhető parlament.hu adat; a hívó tartalékra válthat."""


class CaptchaHiba(UpstreamHiba):
    """A parlament.hu CAPTCHA-választ adott; a hívó tartalékra válthat."""


class HTTPSOnly(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def check_url(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != "https" or u.hostname not in ("www.parlament.hu", "parlament.hu") or u.port not in (None, 443) or u.username or u.password:
        raise ValueError("csak HTTPS parlament.hu adatlekérés engedélyezett")


def read(url, data, timeout, proxy=None):
    check_url(url)
    # Explicit üres mapping: környezeti HTTP_PROXY/HTTPS_PROXY sem szivárog be.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"https": proxy} if proxy else {}), HTTPSOnly())
    req = urllib.request.Request(url, data=data, headers={
        "User-Agent": UA, **({"Content-Type": "application/json"} if data is not None else {})})
    with opener.open(req, timeout=timeout) as response:
        raw = response.read()
    if b"captcha" in raw[:16000].lower() and raw.lstrip().startswith(b"<"):
        raise CaptchaHiba("a parlament.hu CAPTCHA-ellenőrzést kér a kipróbált kijáraton")
    return raw


def decode_json(raw):
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise UpstreamHiba("a parlament.hu nem JSON-t adott") from None
    if not isinstance(value, dict) or not isinstance(value.get("rows"), list) or not isinstance(value.get("metadata"), dict) or not isinstance(value.get("response"), dict):
        raise UpstreamHiba("a parlament.hu válasza nem Felicitas-adat")
    return value


class Pool:
    def __init__(self):
        self.enabled = os.getenv("PARL_PROXY_POOL", os.getenv("ECHOLOT_PROXY_POOL", "1")).lower() not in ("0", "false", "no", "off")
        self.list_url = os.getenv("PARL_PROXY_POOL_URL", os.getenv("ECHOLOT_PROXY_POOL_URL", "https://raw.githubusercontent.com/iplocate/free-proxy-list/main/all-proxies.txt"))
        self.memo_s = 1200
        self.cooldown_s = 900
        self.sample = 40
        self.workers = 12
        self.probe_timeout = 4
        self.discovery_s = 12
        self._lock = threading.Lock()
        self._discovery = threading.Lock()
        self._memo = {}
        self._cooldown = {}
        self._list = []
        self._list_at = 0
        self._last_scan = 0
        self._direct_failed_at = 0

    def note_ok(self, proxy):
        with self._lock:
            if proxy:
                self._memo[proxy] = time.monotonic()
                self._cooldown.pop(proxy, None)
            else:
                self._direct_failed_at = 0

    def note_failed(self, proxy):
        with self._lock:
            if proxy:
                self._memo.pop(proxy, None)
                self._cooldown[proxy] = time.monotonic()
            else:
                self._direct_failed_at = time.monotonic()

    def direct_ready(self):
        with self._lock:
            return not self.enabled or not self._direct_failed_at or time.monotonic() - self._direct_failed_at >= self.cooldown_s

    def cached(self, exclude=()):
        with self._lock:
            now = time.monotonic()
            self._memo = {p: t for p, t in self._memo.items() if now - t < self.memo_s}
            self._cooldown = {p: t for p, t in self._cooldown.items() if now - t < self.cooldown_s}
            # A legrégebben használt élő kijárat: tényleges rotáció.
            for p in sorted(self._memo, key=self._memo.get):
                if p not in exclude:
                    self._memo[p] = now
                    return p

    def candidates(self):
        now = time.monotonic()
        if self._list_at and now - self._list_at < 1800:
            return self._list[:]
        self._list_at = now  # sikertelen listaforrást se kérjünk minden híváskor
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(self.list_url, timeout=8) as r:
                lines = r.read(2_000_000).decode("utf-8").splitlines()
            result = []
            for line in lines:
                try:
                    u = urllib.parse.urlsplit(line.strip())
                    if u.scheme == "http" and u.hostname and u.port and not u.username and not u.password and u.path in ("", "/") and not u.query and not u.fragment:
                        result.append(line.strip())
                except ValueError:
                    continue
            self._list = list(dict.fromkeys(result))
        except Exception as exc:
            log.warning("proxylista nem elérhető (%s)", type(exc).__name__)
        return self._list[:]

    def probe(self, proxy):
        try:
            raw = read(PROBE_URL, b'{"pAktivKepviselo":true}', self.probe_timeout, proxy)
            return bool(decode_json(raw)["rows"])
        except Exception:
            return False

    def working_proxy(self, exclude=()):
        if not self.enabled:
            return None
        if proxy := self.cached(exclude):
            return proxy
        # A többi kérés megvárhatja az egyetlen felderítést, korlátos ideig.
        if not self._discovery.acquire(timeout=self.discovery_s + 9):
            return self.cached(exclude)
        try:
            if proxy := self.cached(exclude):
                return proxy
            if self._last_scan and time.monotonic() - self._last_scan < 60:
                return None
            self._last_scan = time.monotonic()
            candidates = self.candidates()
            with self._lock:
                candidates = [p for p in candidates if p not in exclude and p not in self._cooldown]
            random.shuffle(candidates)
            candidates = candidates[:self.sample]
            # A felderítés teljes idejét a listaletöltés és a futó próbák is növelhetik.
            # A mintaszám, szálak és socket-időkorlát minden esetben véges.
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {executor.submit(self.probe, p): p for p in candidates}
                try:
                    found = 0
                    for future in as_completed(futures, timeout=self.discovery_s):
                        p = futures[future]
                        if future.result():
                            self.note_ok(p)
                            found += 1
                            if found >= 4:
                                break
                        else:
                            self.note_failed(p)
                except TimeoutError:
                    pass
                finally:
                    for future in futures:
                        future.cancel()
            log.info("parlament.hu proxyfelderítés: %d jelölt, %d élő kijárat", len(candidates), self.status()["live_exits"])
            return self.cached(exclude)
        finally:
            self._discovery.release()

    def status(self):
        with self._lock:
            now = time.monotonic()
            return {"enabled": self.enabled, "live_exits": sum(now-t < self.memo_s for t in self._memo.values()),
                    "cooldown_count": sum(now-t < self.cooldown_s for t in self._cooldown.values()),
                    "pool_size": len(self._list), "discovering": self._discovery.locked(),
                    "direct_cooldown": bool(self._direct_failed_at and now-self._direct_failed_at < self.cooldown_s)}


POOL = Pool()


def fetch(url, data=None, *, timeout=30, retries=3, json_response=False):
    """Legfeljebb retries adatlekérés; direkt, majd memo/felderítés/rotáció."""
    check_url(url)
    if retries < 1:
        raise ValueError("retries legalább 1")
    tried = set()
    last = None
    captcha = None
    for attempt in range(retries):
        direct = (attempt == 0 and POOL.direct_ready()) or (not POOL.enabled and not captcha)
        proxy = None if direct else POOL.working_proxy(tried)
        if proxy is None and not direct:
            break
        if proxy:
            tried.add(proxy)
        try:
            raw = read(url, data, timeout, proxy)
            value = decode_json(raw) if json_response else raw.decode("utf-8", "replace")
            POOL.note_ok(proxy)
            return value
        except urllib.error.HTTPError as exc:
            code = exc.code
            exc.close()
            if code not in (403, 407, 408, 429, 500, 502, 503, 504):
                raise UpstreamHiba(f"parlament.hu HTTP {code}") from None
            last = UpstreamHiba(f"parlament.hu HTTP {code}")
        except (CaptchaHiba, UpstreamHiba, OSError, ValueError) as exc:
            if isinstance(exc, CaptchaHiba):
                captcha = exc
            last = UpstreamHiba(f"parlament.hu lekérési hiba ({type(exc).__name__})")
        POOL.note_failed(proxy)
        log.warning("parlament.hu kijárat sikertelen (%s), próbálkozás %d/%d", "proxy" if proxy else "direkt", attempt + 1, retries)
    if captcha:
        raise captcha from None
    raise last or UpstreamHiba("nincs elérhető parlament.hu kijárat; a proxykészlet később újrapróbálható")
