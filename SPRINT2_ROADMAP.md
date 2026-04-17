# Sprint 2 — Roadmap és TODO

## Cél

A **Layer 2 strukturált adatrétegek** (YAML fájlok) teljes feltöltése pontos,
ellenőrzött tartalommal a jelenleg hatályos magyar Házszabály alapján.

Ez az a munka, ahol **jogászi szem kell**: nem csak szöveget másolunk át,
hanem strukturáljuk és §-hivatkozzuk a lényeget.

## Munkamódszer

1. **Forrás**: a hatályos Házszabály letöltése [njt.hu-ról](https://njt.hu/jogszabaly/2014-10-9-30)
   (10/2014. (II.24.) OGY határozat).
2. Olvasás + jegyzetelés + YAML-ba rögzítés.
3. Claus segít a YAML szerkesztésében (formázás, konzisztencia-ellenőrzés).
4. Tamás (mint jogász) végigellenőrzi, hogy a §-hivatkozások stimmelnek-e.

## YAML TODO-lista

### `idokeretek.yaml` — FONTOSSÁGI SORREND

**Kritikus (első körben):**
- [ ] `napirend_elotti` — pontos § megkeresése, idő ellenőrzése
- [ ] `napirend_utani` — teljes blokk feltöltése
- [ ] `azonnali_kerdes` — szereplők és időkeretek pontosítása
- [ ] `kerdes` — szóbeli/írásbeli megkülönböztetése

**Fontos (második körben):**
- [ ] `interpellacio` — teljes folyamat + időkeretek
- [ ] `vezerszonoklat` — frakcióarányos időkeret-rendszer (ez bonyolult!)
- [ ] `vita` — általános vita / részletes vita különbségei

**Kiegészítő:**
- [ ] `szemelyes_nyilatkozat` — pontos feltételek
- [ ] `ugyrendi_felszolalas` — hangsúlyos, mert gyakori

### `hatarido_tabla.yaml`

- [ ] `modosito_inditvany` — pontos határidő, munkanap-számítás
- [ ] `kapcsolodo_modosito`
- [ ] `kerdes_valasz` — írásbeli kérdés válaszadási határideje
- [ ] `interpellacio_valasz`
- [ ] `napirend_kezbesites`
- [ ] `bizottsagi_allaspont`
- [ ] **Új**: `targysorozati_szavazas`
- [ ] **Új**: `kivetel_targyalas_hatarido`

### `eljarasi_folyamatok.yaml`

**Már van vázlat:**
- [ ] `alakulo_ules` — 7 lépés pontos §-hivatkozásokkal
- [ ] `altalanos_ules` — az ülésnap menete

**Feltöltendő:**
- [ ] `torvenyalkotasi_eljaras` — teljes lépéssor (kb. 10-12 lépés)
- [ ] `kivetel_targyalas` — 61. § szerinti sürgősségi eljárás
- [ ] `sarkalatos_torveny` — speciális lépései
- [ ] `bizalmi_szavazas` — konstruktív bizalmatlanság menete
- [ ] **Új**: `koltsegvetes_targyalasa` — külön eljárás!
- [ ] **Új**: `nemzetkozi_szerzodes_kihirdetese`

### `szavazasi_szabalyok.yaml`

Ez a réteg **már most viszonylag precíz** (sarkalatos, alaptörvény-mód. stimmel),
de érdemes kiegészíteni:
- [ ] `hazszabaly_modositas` — 2/3 a jelenlévőkből
- [ ] `haborus_helyzet` + a különleges jogrendi fajták
- [ ] `alkotmanybirok_valasztasa` — jelölőbizottság stb.
- [ ] **Új**: `koztarsasagi_elnok_visszahivasa`
- [ ] **Új**: `eu_csatlakozasi_targyalas`
- [ ] **Új**: `frakcioalapitashoz_szukseges_letszam`

### `glosszarium.yaml`

**Már van 14 fogalom**, bővítsük:
- [ ] `mentelmi_jog`
- [ ] `osszeferhetetlenseg`
- [ ] `vagyonnyilatkozat`
- [ ] `kepviselo_visszahivasa` _(nem létezik magyar jogban — érdemes rögzíteni!)_
- [ ] `bizottsagi_meghallgatas`
- [ ] `kozmeghallgatas`
- [ ] `zaroszavazas`
- [ ] `gyorsitott_eljaras`
- [ ] `kivetelszeruseg`
- [ ] `targysorozati_vita`

## ÚJ YAML-ok (Sprint 2-ben hozandók létre)

### `bizottsagi_szabalyok.yaml` _(ÚJ)_

- Állandó bizottságok listája és főbb feladatuk
- Bizottsági ülés menete
- Bizottsági jelentések típusai
- Vizsgálóbizottságok

### `frakcio_jogok.yaml` _(ÚJ)_

Különösen releváns a barátnőd számára (Tisza-frakciós munkatárs):
- Frakciómegalakítás feltételei (létszám, határidő)
- Frakciójogok részletesen
- Frakcióvezetői előjogok
- Vezérszónoklati időkeret-számítás (matematikai képlet!)
- Bizottsági hely-allokáció (D'Hondt-arány)

### `parlamenti_tisztsegviselok.yaml` _(ÚJ)_

- Házelnök: jogkör, választás, visszahívás
- Alelnökök: frakcióarányos elosztás
- Jegyzők
- Háznagy
- Országgyűlési Hivatal vezetője

### `kulonleges_eljarasok.yaml` _(ÚJ)_

- Költségvetés
- Zárszámadás
- EU-egyeztetési eljárás
- Nemzetközi szerződés kihirdetése
- Különleges jogrend kinyilvánítása

## Sprint 3 előkészítése

Már Sprint 2 során érdemes gyűjteni:

1. **Házszabály teljes szövege** — njt.hu-ról letöltés, szekcióra bontás.
2. **Alaptörvény** parlamenti vonatkozású cikkei — (4., 5., 21., S), T) cikkek).
3. **2012. évi XXXVI. tv.** — teljes szöveg.
4. **Általános parlamenti jog** bibliográfia — Kukorelli, Petrétei, Smuk, stb.

A Sprint 3-ban ezeket chunkoljuk, embeddeljük ChromaDB-be.

## Becsült időigény

- Sprint 2 alapos kurálás: **4-6 munka-délután**, ebből ~2 délután jogász-kontroll.
- Ha intenzívebben: egy hétvége alatt kipréselhető.

## Következő lépés

1. Tamás: Railway-re deploy, GitHub repó létrehozása.
2. Tamás: Friss Házszabály PDF/HTML letöltése az njt.hu-ról.
3. Claus + Tamás együtt: első 3 YAML (idokeretek, hatarido, szavazasi) végig.
4. Éles teszt: a barátnő kipróbálja a ChatGPT-ben, visszajelzés.
5. Iteráció a visszajelzések alapján.
