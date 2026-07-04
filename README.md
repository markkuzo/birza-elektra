# Biržos elektra · LT

Nord Pool Lietuvos zonos biržos elektros kainos **realiu laiku (15 min)** tavo iPhone: gyvas kainos matuoklis, paros juosta, kreivė, statistika, rekomendacijos kada naudoti daugiau/mažiau elektros, rytojaus kainos, orientacinė kelių dienų prognozė ir **įspėjimai apie pigią elektrą**.

Skirta Ignitis „Išmanus–15“ (arba bet kuriam su birža susietam 15 min planui).

---

## Kaip veikia kaina

Programėlė rodo dvi kainas:

- **Biržos kaina** — tikra Nord Pool LT zonos didmeninė kaina (iš Elering API), perskaičiuota iš €/MWh į ct/kWh. Būtent ši kreivė lemia, **kada** apsimoka naudoti elektrą.
- **Galutinė kaina** — kiek realiai moki: `(biržos kaina + tiekėjo marža) × PVM + ESO ir valstybės dedamosios`.

> Laiko sprendimai (kada skalbti, kada krauti EV) priklauso **tik nuo biržos kreivės** — jie teisingi net jei fiksuotas dedamąsias tikslinsi vėliau. Dedamosios keičia tik absoliutų € lygį, ne formą.

### Nustatyk savo dedamąsias (Nustatymai app'e)

| Laukas | Ką įrašyti | Kur rasti |
|---|---|---|
| Tiekėjo marža | Ignitis „Išmanus–15“ marža, ct/kWh **be PVM** | Ignitis savitarna → sutartis / sąskaita |
| ESO + valstybės dedamosios | persiuntimas + VIAP + skirstymo dedamoji, ct/kWh **su PVM** | žr. žemiau |
| PVM | 21 | — |
| Pigios kainos slenkstis | galutinė ct/kWh, žemiau kurios laikoma „pigu“ + siunčiamas įspėjimas | tavo sprendimas (numatyta 10) |

**Kokį ESO planą turi?** Patikrink Ignitis savitarnoje (ties objektu → ESO tarifų planas) arba ESO savitarnoje. Trys buitiniai planai 2026 m.: **Standartinis** (be mėnesinio mokesčio, didesnis ct/kWh — butams/mažai vartojantiems), **Namai** (~3 €/mėn + mažesnis ct/kWh — vidutiniam namų ūkiui), **Namai plius** (didesnis mėn. mokestis, mažiausias ct/kWh — daug vartojantiems). Tikslų persiuntimo ct/kWh savo planui ir laiko zonai rasi ESO 2026 m. tarifų lentelėje — sudėk persiuntimą + VIAP (šiuo metu neigiama, ~−0,05 ct) + papildomą skirstymo dedamąją (~0,03 ct) ir įrašyk sumą su PVM. Numatyta `6,5 ct/kWh` yra apytikslė Standartinio 1 laiko zonos reikšmė — **patikslink**.

---

## Paleidimas per GitHub Pages (nemokamai)

1. Sukurk naują **public** GitHub repo (pvz. `birza-elektra`).
2. Įkelk visus šiuos failus (išsaugok struktūrą):
   ```
   index.html
   manifest.webmanifest
   sw.js
   icons/…
   data/prices.json
   scripts/fetch_prices.py
   .github/workflows/prices.yml
   ```
3. Repo **Settings → Pages → Build and deployment → Source: Deploy from a branch**, šaka `main`, katalogas `/ (root)`. Išsaugok.
4. Po ~1 min tavo app bus adresu `https://<vardas>.github.io/birza-elektra/`.

### Įsidiek į iPhone (PWA)
Safari → atidaryk adresą → **Share** → **Add to Home Screen**. Atsiras piktograma, app veiks per visą ekraną ir be interneto rodys paskutines kainas.

---

## Pranešimai apie kainos kritimą

### A variantas — app viduje (paprasčiausia)
Nustatymuose įjunk **„Įspėjimai apie kritimą“** ir paspausk **„Leisti pranešimus“**. Kai kaina nukrenta žemiau slenksčio, gausi pranešimą — **kol app atidaryta arba veikia fone**. iPhone tai nėra 100 % patikima, kai app visai uždaryta.

### B variantas — ntfy + GitHub Actions (patikimi push, rekomenduojama)
Repo esantis darbas (`prices.yml`) kas 15 min pats paima kainas ir, radęs pigų langą artimiausioms 24 h, siunčia push į tavo telefoną per **ntfy** — jokio savo serverio nereikia.

1. Įsidiek **ntfy** app (App Store, nemokama).
2. Sugalvok privačią, sunkiai atspėjamą temą, pvz. `marius-birza-7h2k9x`. Ntfy app'e → **Subscribe to topic** → įrašyk tą pačią temą.
3. GitHub repo → **Settings → Secrets and variables → Actions → New repository secret**:
   - `NTFY_TOPIC` = `marius-birza-7h2k9x` (ta pati tema)
   - (nebūtina) `NTFY_SERVER` jei naudoji savą ntfy serverį
4. Repo → **Actions** skirtukas → įjunk workflow'us, jei prašo → paleisk **„Kainos ir įspėjimai“ → Run workflow** kartą rankiniu būdu, kad patikrintum.
5. Toliau veiks automatiškai. Gausi push, kai atsiras pigus langas (aukšto prioriteto, jei jis prasideda per artimiausią valandą).

> Pastaba: ntfy temos pavadinimas = slaptažodis. Kas jį žino, gali siųsti/žiūrėti tavo pranešimus, todėl padaryk jį ilgą ir atsitiktinį.

Slenkstį ir dedamąsias workflow'ui keisk faile `.github/workflows/prices.yml` (skiltis `env:`) — kad sutaptų su app nustatymais.

---

## Duomenų šaltinis ir CORS

App pirmiausia bando gauti kainas tiesiai iš Elering API naršyklėje. Jei tai nepavyksta (CORS/ryšys), automatiškai naudoja `data/prices.json`, kurį atnaujina GitHub Action. Todėl **verta įjungti B variantą** — jis vienu metu ir siunčia pranešimus, ir yra atsarginis duomenų šaltinis.

Elering API (be rakto): `https://dashboard.elering.ee/api/nps/price?start=…&end=…` → laukas `data.lt`, kaina €/MWh be PVM.

---

## Failų paskirtis

- `index.html` — visa programėlė (HTML+CSS+JS viename, be build'o).
- `sw.js` — service worker: offline app apvalkalas, kainos visada iš tinklo.
- `manifest.webmanifest` + `icons/` — PWA (Home Screen piktograma, pilnas ekranas).
- `scripts/fetch_prices.py` — kainų surinkėjas + ntfy įspėjimai (naudoja Action).
- `.github/workflows/prices.yml` — automatinis paleidimas kas 15 min.
- `data/prices.json` — kainų momentinė kopija (perrašoma Action'o).

Techninis planas gali skirtis nuo galutinio; jei kas neveikia, patikrink Actions logą (repo → Actions → paskutinis paleidimas).
