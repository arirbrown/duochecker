#!/usr/bin/env python3
"""Polls Apple's in-store pickup availability for iPhone Duo 512GB in NYC and Boston stores and alerts on stock."""
import argparse
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

PARTS = {
    "MK1H4LL/A": "iPhone Duo 512GB Night Sky",
    "MK1G4LL/A": "iPhone Duo 512GB Star White",
}

# Each zip returns the 12 nearest stores; together these cover all 12 NYC stores and central Boston.
QUERY_ZIPS = ["10001", "11201", "02116"]

STORES = {
    "R250": "West 14th Street, NYC",
    "R415": "Grand Central, NYC",
    "R032": "SoHo, NYC",
    "R095": "Fifth Avenue, NYC",
    "R251": "Upper West Side, NYC",
    "R582": "Upper East Side, NYC",
    "R654": "World Trade Center, NYC",
    "R594": "Williamsburg, Brooklyn",
    "R715": "Downtown Brooklyn, Brooklyn",
    "R612": "Queens Center, Queens",
    "R753": "The Mall at Bay Plaza, Bronx",
    "R152": "Staten Island, Staten Island",
    "R149": "Boylston Street, Boston",
    "R021": "CambridgeSide, Cambridge",
    "R076": "Chestnut Hill, Chestnut Hill",
}

BUY_URLS = {
    "MK1H4LL/A": "https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-night-sky-unlocked",
    "MK1G4LL/A": "https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-star-white-unlocked",
}

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
PICKUP_URL = "https://www.apple.com/shop/retail/pickup-message"


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}Z] {msg}", flush=True)


def http(url, data=None, headers=None, timeout=20):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def fetch_zip(zip_code):
    params = [("pl", "true"), ("location", zip_code)]
    params += [(f"parts.{i}", p) for i, p in enumerate(PARTS)]
    _, body = http(f"{PICKUP_URL}?{urllib.parse.urlencode(params)}", headers={"Accept": "application/json"})
    return json.loads(body)["body"]["stores"]


def check():
    """Returns {(store_number, part): quote} for every in-stock watched combo, and number of stores seen."""
    in_stock, seen = {}, set()
    for z in QUERY_ZIPS:
        for s in fetch_zip(z):
            num = s.get("storeNumber")
            if num not in STORES:
                continue
            seen.add(num)
            for part, a in (s.get("partsAvailability") or {}).items():
                if part in PARTS and a.get("pickupDisplay") == "available":
                    in_stock[(num, part)] = a.get("pickupSearchQuote") or "Available"
    return in_stock, seen


def format_alert(new):
    lines = ["iPhone Duo 512GB IN STOCK for pickup:"]
    for (store, part), quote in sorted(new.items()):
        lines.append(f"- {PARTS[part]} @ Apple {STORES[store]} ({quote})")
    for part in sorted({p for _, p in new}):
        lines.append(f"Buy: {BUY_URLS[part]}")
    return "\n".join(lines)


# ---------- notifiers ----------

def notify_callmebot(text):
    # CALLMEBOT_RECIPIENTS="+19175551234:123456,+16175559876:654321"
    for entry in filter(None, (e.strip() for e in os.getenv("CALLMEBOT_RECIPIENTS", "").split(","))):
        phone, _, key = entry.partition(":")
        q = urllib.parse.urlencode({"phone": phone.strip(), "text": text, "apikey": key.strip()})
        try:
            status, body = http(f"https://api.callmebot.com/whatsapp.php?{q}", timeout=30)
            log(f"callmebot -> ...{phone.strip()[-4:]}: HTTP {status} {body[:120]!r}")
        except Exception as e:
            log(f"callmebot -> ...{phone.strip()[-4:]} failed: {e}")


def notify_telegram(text):
    # TELEGRAM_CHAT_ID can be a group id or a comma-separated list of chat ids.
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chats = [c.strip() for c in os.getenv("TELEGRAM_CHAT_ID", "").split(",") if c.strip()]
    if not token:
        return
    for chat in chats:
        data = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
        try:
            status, _ = http(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
            log(f"telegram -> {chat}: HTTP {status}")
        except Exception as e:
            log(f"telegram -> {chat} failed: {e}")


def notify_ntfy(text):
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return
    try:
        status, _ = http(f"https://ntfy.sh/{topic}", data=text.encode(),
                         headers={"Title": "iPhone Duo in stock", "Priority": "urgent", "Tags": "iphone,rotating_light"})
        log(f"ntfy: HTTP {status}")
    except Exception as e:
        log(f"ntfy failed: {e}")


def notify_twilio(text):
    sid, tok, frm = os.getenv("TWILIO_ACCOUNT_SID"), os.getenv("TWILIO_AUTH_TOKEN"), os.getenv("TWILIO_FROM")
    to_list = [t.strip() for t in os.getenv("TWILIO_TO", "").split(",") if t.strip()]
    if not (sid and tok and frm and to_list):
        return
    import base64
    auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
    for to in to_list:
        data = urllib.parse.urlencode({"From": frm, "To": to, "Body": text}).encode()
        try:
            status, _ = http(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", data=data,
                             headers={"Authorization": f"Basic {auth}"})
            log(f"twilio -> ...{to[-4:]}: HTTP {status}")
        except Exception as e:
            log(f"twilio -> ...{to[-4:]} failed: {e}")


def notify(text):
    for fn in (notify_callmebot, notify_telegram, notify_ntfy, notify_twilio):
        fn(text)


# ---------- main loop ----------

def load_state(path):
    try:
        with open(path) as f:
            return {tuple(k.split("|")) for k in json.load(f)}
    except (OSError, ValueError):
        return set()


def save_state(path, keys):
    with open(path, "w") as f:
        json.dump(sorted("|".join(k) for k in keys), f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=int(os.getenv("CHECK_INTERVAL", "5")))
    ap.add_argument("--duration", type=int, default=int(os.getenv("RUN_DURATION", "0")),
                    help="seconds to keep looping (0 = forever)")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--state", default=os.getenv("STATE_FILE", "state.json"))
    ap.add_argument("--test-notify", action="store_true", help="send a test message and exit")
    args = ap.parse_args()

    if args.test_notify:
        notify("duochecker test: alerts are working. You'll get a message like this when an iPhone Duo "
               "512GB (Night Sky or Star White) is available for pickup in NYC or Boston.")
        return

    drill = os.getenv("DRILL_PART")
    if drill:
        PARTS[drill] = "DRILL item (not an iPhone)"
        BUY_URLS[drill] = f"https://www.apple.com/shop/product/{drill}"

    channels = [name for name, var in (("whatsapp", "CALLMEBOT_RECIPIENTS"), ("telegram", "TELEGRAM_BOT_TOKEN"),
                                       ("ntfy", "NTFY_TOPIC"), ("sms", "TWILIO_TO")) if os.getenv(var)]
    log(f"alert channels: {', '.join(channels) or 'NONE (set secrets!)'}; checking every {args.interval}s")

    known = load_state(args.state)
    deadline = time.time() + args.duration if args.duration else None
    failures = checks = 0
    while True:
        checks += 1
        try:
            in_stock, seen = check()
            failures = 0
            current = set(in_stock)
            new = {k: v for k, v in in_stock.items() if k not in known}
            if new or checks % 60 == 1:
                log(f"checked {len(seen)} stores: {len(current)} in stock, {len(new)} new")
            if new:
                msg = format_alert(new)
                if drill:
                    msg = "DRILL, NOT REAL STOCK. This is a test of the stock alert path.\n" + msg
                log(msg)
                notify(msg)
            gone = known - current
            if gone:
                log("sold out again: " + ", ".join(f"{PARTS[p]} @ {STORES[s]}" for s, p in sorted(gone)))
            known = current
            save_state(args.state, known)
        except Exception as e:
            failures += 1
            log(f"check failed ({failures}): {e}")
        # Back off (up to 5 min) if Apple starts erroring or rate-limiting.
        wait = min(300, args.interval * 2 ** failures) if failures else args.interval
        if args.once or (deadline and time.time() + wait > deadline):
            log(f"done: {checks} checks, {failures} failing at exit")
            break
        time.sleep(wait)


if __name__ == "__main__":
    sys.exit(main())
