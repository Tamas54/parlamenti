# Parlamentaris Kompendium — Kezdőknek

## Mi ez?

Egy ChatGPT-re rákapcsolható "tudós segéd", aki pontosan ismeri a
magyar Országgyűlés működését: Házszabályt, Alaptörvényt, eljárási
szabályokat, időkereteket, határidőket.

Amikor a ChatGPT-d használja, ő **nem találgat** — mindenre pontos
jogszabályi hivatkozással válaszol.

## Mire jó?

Példa kérdések, amiket a ChatGPT-nek felteheted, és amikre jó választ kapsz:

- "Hány perce van egy képviselőnek napirend előtti felszólalásra?"
- "Hogyan zajlik egy alakuló ülés?"
- "Mi a különbség az interpelláció és a kérdés között?"
- "Milyen többség kell az Alaptörvény módosításához?"
- "Mi az a vezérszónoklat?"
- "Ki a korelnök és mit csinál?"
- "Hogyan működik a konstruktív bizalmatlansági indítvány?"
- "Milyen határidővel lehet módosító indítványt benyújtani?"

## Hogyan kapcsolom rá a ChatGPT-re?

### 1. lépés — Developer Mode bekapcsolása

1. ChatGPT-ben kattints a profilképedre → **Settings**.
2. Bal oldali menü: **Connectors** (régen Apps).
3. Lent: **Advanced settings** → **Developer mode** kapcsold **ON**-ra.
4. Figyelmeztető ablak jön — fogadd el.

### 2. lépés — Connector hozzáadása

1. Ugyanott: **Add new connector** (vagy **Create**).
2. Töltsd ki:
   - **Name**: `Parlamentaris Kompendium`
   - **Description**: `Magyar Országgyűlési eljárásjogi tudásbázis`
   - **MCP Server URL**: _(az URL, amit Tamástól kapsz)_
   - **Authentication**: `None`
3. Jelöld be: "I trust this application".
4. **Create**.

### 3. lépés — Használat

Minden új chat elején:

1. A szövegbeviteli mező mellett a **+** gombra kattints.
2. Válaszd a **Developer mode**-ot.
3. A listából jelöld be a **Parlamentaris Kompendium**-ot.
4. Most már használhatod a chat teljes hosszában.

## Tippek a jobb eredményért

**Ahelyett, hogy:**
> "mondd el a házszabályt"

**Inkább:**
> "Hány perces időkeret áll rendelkezésre a miniszterelnöknek napirend
> előtti felszólalásra, és válaszolhat-e?"

**Ahelyett, hogy:**
> "mi van a választás után"

**Inkább:**
> "Lépésről lépésre hogyan zajlik az Országgyűlés alakuló ülése?"

**A ChatGPT megmondja a forrást is!** Ha nem mutatja magától, kérdezz rá:
> "Mi a jogszabályi hivatkozás?"

## Fontos tudnivaló

Ez egy **segédeszköz**, nem jogi állásfoglalás. Ha komoly kérdés van, mindig
ellenőrizd a megadott jogforrást (§-számot) a [njt.hu](https://njt.hu) oldalon.

## Mit tud még?

Kérdezd meg:
> "Mit tudsz csinálni? Miket tartalmazol?"

A `szerver_info` tool fog válaszolni neked a részletes képességekről.

## Ha valami nem működik

- Ellenőrizd, hogy a Developer Mode be van-e kapcsolva.
- Ellenőrizd, hogy a chat elején bejelölted-e a connectort.
- Ha hibát ír, kérdezd meg a ChatGPT-t: "mit próbáltál? add az MCP válasz pontos
  szövegét" — és küldd el Tamásnak.
