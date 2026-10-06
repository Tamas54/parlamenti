# Parlamentaris Kompendium MCP

**Magyar Orszaggyulesi eljarasjogi tudasbazis -- MCP szerverkent, ChatGPT + Claude + barmely MCP-kliens szamara.**

Remote MCP szerver, amely a magyar Alaptorvenyt, a Hazszabalyt (10/2014. OGY hat.),
es az Orszaggyulesrol szolo 2012. evi XXXVI. torvenyt szolgaltatja
**strukturalt, hallucinacio-mentes** formaban, valodi jogszabalyszovegekbol.

## Elo szerver

```
https://parlamenti-production.up.railway.app/mcp
```

Dashboard: https://parlamenti-production.up.railway.app

Ki kicsoda (kepviselok, partok, jelenlegi bizottsagi tagsagok, ulesrend/patko — nyomtathato, linkelheto):
https://parlamenti-production.up.railway.app/kepviselok
(ulesrend: `/kepviselok?nezet=ulesrend`, egy kepviselo helye: `?nezet=ulesrend&sel=<id>`)

---

## Integralas ChatGPT-be

### 1. Nyisd meg a Connectors beallitasokat

**Settings > Connectors** (bal also sarok fogaskerek > Connectors)

### 2. Hozz letre uj alkalmazast

Kattints az **"Alkalmazas letrehozasa"** gombra (vagy "Tovabbiak hozzaadasa"),
majd toltsd ki:

| Mezo | Ertek |
|------|-------|
| **Nev** | `Parlamentaris Kompendium` |
| **Leiras** | `Magyar Orszaggyulesi eljarasjogi tudasbazis` |
| **MCP szerver URL** | `https://parlamenti-production.up.railway.app/mcp` |
| **Hitelesites** | `Nincs engedelyezve` |

Mentsd el.

### 3. Hasznald chatben

1. Nyiss **uj chat**-et
2. Az uzenetmezo mellett a **"+"** ikonra kattints
3. Valaszd ki a **"Parlamentaris Kompendium"** connectort
4. Kerdezz barmi parlamentariset!

**Pelda promptok:**
- "Hany perce van a miniszterelnoknek napirend elotti felszolalasra?"
- "Hogyan zajlik az alakulo ules?"
- "Milyen tobbseg kell az Alaptorveny modositasahoz?"
- "Mi az a vezerszonoklat?"
- "Keress a Hazszabalyban az interpellacios eljarasra"

---

## Integralas Claude-ba (Claude Code / claude.ai)

### Claude Code CLI

Add hozza a `~/.claude/settings.json`-hoz:

```json
{
  "mcpServers": {
    "parlamenti": {
      "type": "url",
      "url": "https://parlamenti-production.up.railway.app/mcp"
    }
  }
}
```

### claude.ai (MCP connector)

A claude.ai Integrations felulet alatt add hozza mint remote MCP server:
- URL: `https://parlamenti-production.up.railway.app/mcp`

---

## Tool-ok

### Idokeretek es hataridok (strukturalt YAML)
| Tool | Mit csinal |
|------|------------|
| `get_idokeret(szituacio, szereplo)` | Felszolalasi idokeret pontos percben |
| `get_hatarido(esemeny)` | Benyujtasi, valaszadasi hataridok |
| `list_idokeret_szituaciok()` | Elerheto szituaciok listaja |

### Eljarasi folyamatok
| Tool | Mit csinal |
|------|------------|
| `get_eljarasi_folyamat(tipus, reszletesseg)` | Folyamatok lepesrol lepesre |
| `list_eljarasi_folyamatok()` | Ismert folyamatok katalogusa |
| `get_szavazasi_szabalyok(targykor)` | Szavazasi tobbsegi kovetelmenyek |

### Kereses a jogszabalyszovegekben (TF-IDF)
| Tool | Mit csinal |
|------|------------|
| `search_hazszabaly(query, top_k)` | Hazszabaly teljes szoveg |
| `search_alaptorveny(query, top_k)` | Alaptorveny teljes szoveg |
| `search_ogy_torveny(query, top_k)` | 2012. evi XXXVI. tv. teljes szoveg |
| `search_altalanos_parlamenti_jog(query, top_k)` | Altalanos parlamenti jog |
| `search_all(query, top_k)` | Kereses minden korpuszban |

### Fogalomtar
| Tool | Mit csinal |
|------|------------|
| `magyarazd_el(fogalom)` | Szakszomagyarazat kezdobarat nyelven |
| `list_fogalmak()` | Glosszarium tartalma |

### Meta
| Tool | Mit csinal |
|------|------------|
| `szerver_info()` | Szerver-info, adatforrasok, verzio |

### Kepviselok: ki kicsoda, ki mivel foglalkozott (parlament.hu, 6 orankent frissitve)
| Tool | Mit csinal |
|------|------------|
| `kepviselo_adatok(nev)` | Frakcio, valasztokerulet, tisztsegek, jelenlegi bizottsagi tagsagok, rovid tevekenyseg-osszesito |
| `bizottsag_tagjai(bizottsag)` | Egy bizottsag jelenlegi tagjai tisztseggel es frakcioval |
| `kepviselo_tevekenyseg(nev, reszletek, limit)` | Mivel foglalkozott: sulyozott temak, onallo inditvanyok, modositok, felszolalasok (linkkel) |
| `ki_foglalkozott(tema, limit)` | Egy temaval kik foglalkoztak (inditvany, modosito, felszolalas), rangsorolva |
| `felszolalas_kereses(szoveg, kepviselo, limit)` | Elo kereses a felszolalasok SZOVEGEBEN, ki hanyszor mondta |

Web: `/kepviselok?nezet=tevekenyseg` (Ki mivel foglalkozott), kepviselo-lapon „Mivel foglalkozott” blokk.

---

## Architektura

```
  Layer 2: STRUKTURALT KURALT ADATOK (YAML)
  Idokeretek, hataridok, szavazasi szabalyok
  --> pontos szamok, nincs hallucinacio
  ─────────────────────────────────────────
  Layer 1: TELJES JOGSZABALYSZOVEG (552 chunk)
  Hazszabaly (323) + Alaptorveny (75) + OGY tv (154)
  --> TF-IDF kereses, valos §-hivatkozasok
  ─────────────────────────────────────────
  Layer 0: FOGALOMTAR + FOLYAMATOK
  Glosszarium, eljarasi folyamatok lepesrol lepesre
```

**Forrasok:**
- Hazszabaly: parlament.hu (365 oldalas bov. kiadas, 2026.01.31. lezaras)
- Alaptorveny: jogtar.hu (hatalyos szoveg)
- OGY tv: jogtar.hu (2012. evi XXXVI. tv., hatalyos szoveg)
- Kepviselok / bizottsagok: parlament.hu felicitas API (`src/kepviselok.py`), 6 orankent
  hatterben frissul; a `src/data/kepviselok.json` snapshot a tartalek. A bizottsagi tagsagot
  szemelyenkent, a tagsag vege-datumabol rakja ossze (a parlament.hu bizottsagi nevsora a
  ciklus megszunt tagsagait is listazza). Kezi frissites: `PYTHONPATH=src python src/kepviselok.py`

---

## Fejlesztes helyben

```bash
git clone https://github.com/Tamas54/parlamenti.git
cd parlamenti
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src python src/server.py
# --> http://localhost:8000/mcp
# --> http://localhost:8000/ (dashboard)
```

---

## Figyelmezetes

Ez egy **kutatasi es tajekoztatasi segedeszk0z**. Jogi allasfoglalasnak NEM
minosul. Minden kritikus dontes elott ellenorizd a jogforrast a megadott
hivatkozason.

## Licenc

MIT

## Parlament.hu proxyrotáció

A `src/parlament_proxy.py` az Echolot `echolot_proxy.py` készletének mintáját
adaptálja a parlament.hu Felicitas API-jára (forrás: Hirmagnetmcp, d2b649b).
A közös `_post` és `_get_text` használja, ezért a képviselő- és tevékenységfrissítés,
az élő felszólaláskeresés és az SVG-letöltés is ugyanazt a kijáratkészletet kapja.

- Először direkt kapcsolat; CAPTCHA, tiltás, átmeneti HTTP-/hálózati hiba vagy
  hibás JSON után ellenőrzött proxy. Legfeljebb 3 adatlekérési próbálkozás.
- Ingyenes iplocate-lista, 30 perces cache. Felderítésenként legfeljebb 40 jelölt,
  12 szál, 4 másodperces socket-timeout, 12 másodperces eredménygyűjtés.
  A listaletöltés (legfeljebb 8 s) és a már futó próbák befejezése ezt növelheti;
  ez nem a teljes HTTP-kérésre érvényes határidő.
- A próba valódi, olvasási Felicitas POST; legfeljebb 4 működő kijáratot gyűjt.
  A sikeres kijáratok rotálnak, 20 perces memóval; hibánál 15 perc hűtés.
  Egyszerre egy felderítés futhat; sikertelen felderítés után 60 s szünet.
- Csak HTTPS parlament.hu cél, ellenőrzött TLS-sel, HTTP CONNECT proxyn.
  A helyi frissítő kulcsos feltöltése nem használja ezt a proxyréteget.
- `PARL_PROXY_POOL=0` kikapcsolja. A listaforrás `PARL_PROXY_POOL_URL`-lel
  állítható; az Echolot változónevei is támogatottak (lásd `.env.example`).
  A környezeti változókat induláskor olvassa; a `.env` fájlt nem tölti be magától.
- A `/health` `proxy` mezője címek és hitelesítő adatok nélkül mutatja a készlet
  állapotát. Működő proxy nem garantált; a snapshot és a helyi feltöltő megmarad.

Teszt: `python -m unittest discover -s tests -v` (hálózat nélkül).
