# Parlamentaris Kompendium MCP

**Magyar Országgyűlési eljárásjogi tudásbázis — MCP szerverként, ChatGPT + Claude + bármely MCP-kliens számára.**

Egy Remote MCP szerver, amely a magyar Alaptörvény parlamenti rendelkezéseit,
a Házszabályt (10/2014. (II.24.) OGY hat.), az Országgyűlésről szóló
2012. évi XXXVI. törvényt, és az általános parlamenti jogi alapelveket
szolgáltatja **strukturált, hallucináció-mentes** formában.

## Miért épült?

Nem jogász frakciómunkatársaknak, képviselői asszisztenseknek, sajtósoknak,
civil politikai elemzőknek — hogy egy ChatGPT / Claude prompt-ra pontos,
§-hivatkozással ellátott választ kapjanak olyan kérdésekre, mint:

- "Hány perce van a miniszterelnöknek napirend előtti felszólalásra?"
- "Hogyan zajlik az alakuló ülés?"
- "Milyen többség kell az Alaptörvény módosításához?"
- "Mi az a vezérszónoklat? Miben különbözik a sima felszólalástól?"
- "Milyen határidővel kell benyújtani a módosító indítványt?"

## Architektúra — négyrétegű tudásbázis

```
┌─────────────────────────────────────────────────────┐
│  Layer 3: PRECEDENSEK & FRAKCIÓSZABÁLYOK            │
│  Elnöki döntvények, bevett gyakorlat                │
├─────────────────────────────────────────────────────┤
│  Layer 2: STRUKTURÁLT KURÁLT ADATOK (YAML)          │
│  Időkeretek, határidők, folyamatok, szavazási       │
│  szabályok, glosszárium → pontos számok, nincs      │
│  hallucináció                                        │
├─────────────────────────────────────────────────────┤
│  Layer 1: TELJES SZÖVEGKORPUSZ (ChromaDB RAG)       │
│  Alaptörvény, Házszabály, OGY tv. — szemantikus     │
│  keresés magyar multilingual embedderrel            │
├─────────────────────────────────────────────────────┤
│  Layer 0: ÁLTALÁNOS PARLAMENTI JOG                  │
│  Időtálló, absztrakt jogtudományi réteg             │
└─────────────────────────────────────────────────────┘
```

**A kulcsötlet**: a konkrét számokat (időkeretek, határidők, létszámok) SOHA
nem RAG-ból adjuk vissza — azok kézzel kurált YAML-ban vannak, forráshivatkozással.
Csak a hosszabb, narratív kérdésekre válaszol a RAG.

## Tool-ök (14 db)

### Időkeretek és határidők (strukturált)
- `get_idokeret(szituacio, szereplo)` — felszólalási időkeret pontos percben
- `get_hatarido(esemeny)` — benyújtási, válaszadási határidők
- `list_idokeret_szituaciok()` — lehetséges szituációk listája

### Eljárási folyamatok
- `get_eljarasi_folyamat(tipus, reszletesseg)` — alakuló ülés, törvényalkotás stb.
- `list_eljarasi_folyamatok()` — ismert folyamatok katalógusa
- `get_szavazasi_szabalyok(targykor)` — többségi követelmények

### Szemantikus keresés (RAG)
- `search_hazszabaly(query, top_k)` — Házszabály szöveg
- `search_alaptorveny(query, top_k)` — Alaptörvény
- `search_ogy_torveny(query, top_k)` — 2012. évi XXXVI. tv.
- `search_altalanos_parlamenti_jog(query, top_k)` — Layer 0
- `search_all(query, top_k)` — keresés minden korpuszban

### Fogalomtár
- `magyarazd_el(fogalom)` — kezdőbarát szakszó-magyarázat
- `list_fogalmak()` — glosszárium tartalma

### Meta
- `szerver_info()` — szerver-infó, adatforrások, verzió

## Telepítés Railway-re

### 1. GitHub repó létrehozása

```bash
git init
git add .
git commit -m "Parlamentaris Kompendium MCP — Sprint 1 skeleton"
git branch -M main
git remote add origin https://github.com/YOUR_USER/parlamentaris-kompendium-mcp.git
git push -u origin main
```

### 2. Railway projekt

1. Menj a [Railway.app](https://railway.app) oldalra, jelentkezz be.
2. "New Project" → "Deploy from GitHub repo" → válaszd ki a repót.
3. Railway automatikusan felismeri a Dockerfile-t és buildel.
4. A `Settings → Networking` alatt generálj egy publikus domaint:
   pl. `parlamentaris-kompendium-production.up.railway.app`
5. A szerver így lesz elérhető:
   `https://parlamentaris-kompendium-production.up.railway.app/mcp`

### 3. ChatGPT connector hozzáadása

A barátnőd teendői a ChatGPT-ben:

1. **Settings → Connectors → Advanced settings → Developer Mode: ON**
2. "Add new connector" vagy "Create connector"
3. Név: `Parlamentaris Kompendium`
4. Leírás: `Magyar Országgyűlési eljárásjogi tudásbázis`
5. MCP Server URL: `https://<a-railway-urled>/mcp`
6. Authentication: `None` (publikus, de titkos URL)
7. Mentés

Utána új chat-ben, a "+" menü → "Developer mode" → bejelöli a
`Parlamentaris Kompendium` connectort, és onnantól a ChatGPT használni fogja.

## Fejlesztés helyben

```bash
pip install -r requirements.txt
cd src
python server.py
# → http://localhost:8000/mcp
```

## Állapot

**Sprint 1 — KÉSZ ✓**: Skeleton, 14 tool, kezdő YAML tartalom,
Docker/Railway deployment.

**Sprint 2 — következő**: Házszabály §-hivatkozások teljes ellenőrzése,
YAML-ok feltöltése pontos adatokkal (jogász-kontroll szükséges).

**Sprint 3**: Jogszabályi szövegek letöltése, chunking, ChromaDB
feltöltés, RAG aktiválás.

**Sprint 4**: Polírozás, tool-leírások finomhangolása, barátnő-tesztek.

## Figyelmeztetés

Ez egy **kutatási és tájékoztató segédeszköz**. Jogi állásfoglalásnak NEM
minősül. Minden kritikus döntés előtt ellenőrizd a jogforrást a megadott
§-hivatkozáson.

## Licenc

MIT — szabadon felhasználható, módosítható.
