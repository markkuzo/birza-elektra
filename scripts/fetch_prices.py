#!/usr/bin/env python3
"""
Biržos elektra — kainų surinkėjas (GitHub Actions).

Ką daro:
  1. Paima Nord Pool LT zonos 15 min kainas iš Elering Dashboard API
     (nuo -2 d. iki +2 d. — istorijai, šiandienai ir rytojui).
  2. Įrašo į data/prices.json (tą patį formatą, kokį naudoja app;
     tai atsarginis šaltinis, jei naršyklė neturi CORS prieigos prie Elering).
  3. Jei artimiausiose 24 h atsiranda pigus langas (galutinė kaina <= THRESHOLD_CT),
     nusiunčia pranešimą į ntfy.sh temą -> push į telefoną (ntfy app).
     Būsena saugoma data/notify_state.json, kad nesikartotų tas pats langas.

Aplinkos kintamieji (nustatomi per GitHub Secrets / workflow env):
  NTFY_TOPIC     ntfy temos pavadinimas (pvz. "marius-birza-a8f3"). Jei nenustatyta — pranešimai praleidžiami.
  NTFY_SERVER    numatyta https://ntfy.sh
  THRESHOLD_CT   pigios kainos slenkstis, galutinė ct/kWh (numatyta 8.0)
  MARZA_CT       tiekėjo marža ct/kWh be PVM (numatyta 1.29)
  ESO_CT         ESO + valstybės dedamosios ct/kWh su PVM (numatyta 6.50)
  PVM_PCT        PVM % (numatyta 21)
"""
import os, json, time, datetime, urllib.request, urllib.error, pathlib

REGION      = "lt"
API         = "https://dashboard.elering.ee/api/nps/price"
ROOT        = pathlib.Path(__file__).resolve().parent.parent
DATA_DIR    = ROOT / "data"
OUT_FILE    = DATA_DIR / "prices.json"
STATE_FILE  = DATA_DIR / "notify_state.json"

THRESHOLD_CT = float(os.environ.get("THRESHOLD_CT", "10.0"))
MARZA_CT     = float(os.environ.get("MARZA_CT", "1.29"))
ESO_CT       = float(os.environ.get("ESO_CT", "6.50"))
PVM_PCT      = float(os.environ.get("PVM_PCT", "21"))
NTFY_TOPIC   = os.environ.get("NTFY_TOPIC", "").strip()
NTFY_SERVER  = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")

UA = "birza-elektra-fetcher/1.0 (+github-actions)"


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + ("000Z" if dt.microsecond == 0 else f"{dt.microsecond//1000:03d}Z")


def fetch():
    now = datetime.datetime.now(datetime.timezone.utc)
    start = now - datetime.timedelta(days=2)
    end = now + datetime.timedelta(days=2)
    url = f"{API}?start={iso(start)}&end={iso(end)}"
    req = urllib.request.Request(url, headers={"accept": "application/json", "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        j = json.load(r)
    arr = (j.get("data") or {}).get(REGION) or []
    if not arr:
        raise RuntimeError("Elering grąžino tuščią LT sąrašą")
    # normalize
    return [{"timestamp": int(x["timestamp"]), "price": float(x["price"])} for x in arr]


def final_ct(mwh):
    spot = mwh / 10.0                       # EUR/MWh -> ct/kWh (be PVM)
    return (spot + MARZA_CT) * (1 + PVM_PCT / 100.0) + ESO_CT


def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {"notified": []}


def save_state(st):
    STATE_FILE.write_text(json.dumps(st))


def ntfy(title, body, priority="default", tags="zap"):
    if not NTFY_TOPIC:
        print("NTFY_TOPIC nenustatyta — pranešimas praleistas:", title)
        return
    url = f"{NTFY_SERVER}/{NTFY_TOPIC}"
    data = body.encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers={
        "Title": title.encode("utf-8").decode("latin-1", "ignore"),
        "Priority": priority,
        "Tags": tags,
        "User-Agent": UA,
    })
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read()
        print("ntfy išsiųsta:", title)
    except Exception as e:
        print("ntfy klaida:", e)


def vilnius_label(ts):
    # aproksimacija be zoneinfo: EET/EEST. Bandome zoneinfo, jei yra.
    try:
        from zoneinfo import ZoneInfo
        return datetime.datetime.fromtimestamp(ts, ZoneInfo("Europe/Vilnius")).strftime("%H:%M")
    except Exception:
        # fallback: liepos–rugsėjo mėn. EEST (+3), kitu atveju spėjam +2
        off = 3 if datetime.datetime.utcfromtimestamp(ts).month in (4,5,6,7,8,9,10) else 2
        return datetime.datetime.utcfromtimestamp(ts + off*3600).strftime("%H:%M")


def check_alerts(points):
    now = int(time.time())
    horizon = now + 24 * 3600
    upcoming = [p for p in points if now <= p["timestamp"] <= horizon]
    cheap = [p for p in upcoming if final_ct(p["price"]) <= THRESHOLD_CT]
    st = load_state()
    notified = set(st.get("notified", []))
    # keep only future keys to avoid unbounded growth
    notified = {k for k in notified if k >= now - 6*3600}

    if not cheap:
        save_state({"notified": sorted(notified)})
        return

    # group contiguous cheap slots into windows
    cheap.sort(key=lambda p: p["timestamp"])
    windows = []
    cur = [cheap[0]]
    for p in cheap[1:]:
        if p["timestamp"] - cur[-1]["timestamp"] <= 15*60 + 5:
            cur.append(p)
        else:
            windows.append(cur); cur = [p]
    windows.append(cur)

    for w in windows:
        key = w[0]["timestamp"]  # window identified by its start
        if key in notified:
            continue
        avg = sum(final_ct(p["price"]) for p in w) / len(w)
        mn = min(final_ct(p["price"]) for p in w)
        start_l = vilnius_label(w[0]["timestamp"])
        end_l = vilnius_label(w[-1]["timestamp"] + 15*60)
        mins = max(0, (w[0]["timestamp"] - now) // 60)
        when = "dabar" if mins <= 0 else (f"po {mins} min" if mins < 60 else f"po {mins//60} val {mins%60} min")
        title = f"⚡ Pigi elektra {start_l}–{end_l}"
        body = f"{mn:.1f}–{avg:.1f} ct/kWh · {when}\nGeras metas skalbimui, indaplovei, boileriui ar EV."
        ntfy(title, body, priority=("high" if mins <= 60 else "default"))
        notified.add(key)

    save_state({"notified": sorted(notified)})


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    points = fetch()
    payload = {
        "updated": int(time.time()),
        "source": "elering",
        "region": REGION,
        "unit": "EUR/MWh",
        "params": {"marza_ct": MARZA_CT, "eso_ct": ESO_CT, "pvm_pct": PVM_PCT, "threshold_ct": THRESHOLD_CT},
        "data": {REGION: points},
    }
    OUT_FILE.write_text(json.dumps(payload, separators=(",", ":")))
    print(f"Įrašyta {len(points)} taškų -> {OUT_FILE}")
    try:
        check_alerts(points)
    except Exception as e:
        print("Įspėjimų tikrinimo klaida:", e)


if __name__ == "__main__":
    main()
