# duochecker

Watches Apple's in-store pickup availability for **iPhone Duo 512GB** (Night Sky `MK1H4LL/A`, Star White `MK1G4LL/A`) at every Apple Store in **New York City** (12 stores, all 5 boroughs) and **Boston** (Boylston Street, CambridgeSide, Chestnut Hill). It checks every 5 seconds and sends an alert when a store goes from unavailable to available.

Runs free on GitHub Actions (`.github/workflows/check.yml`): each job loops for about 5h45m, and the next scheduled run waits in the queue to take over, so checking never stops. You're alerted once per store/color when it comes in stock. If that store sells out and restocks, you're alerted again.

## Alerts

Set any of these as repo secrets (Settings → Secrets and variables → Actions → New repository secret):

| Secret | Channel | Value |
|---|---|---|
| `CALLMEBOT_RECIPIENTS` | WhatsApp (free, each person gets their own message) | `+19175551234:APIKEY1,+16175559876:APIKEY2` |
| `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` | Telegram (works with group chats) | bot token from @BotFather; group chat id |
| `NTFY_TOPIC` | Push notification through the ntfy app | a hard-to-guess topic name |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `TWILIO_TO` | SMS (paid; US numbers need A2P/toll-free verification) | `TWILIO_TO` can be comma-separated |

**WhatsApp key (CallMeBot):** save `+34 684 728 023` as a contact, then send it `I allow callmebot to send me messages` on WhatsApp. It replies with your API key. Each person who wants alerts does this on their own phone.

**Test alerts:** Actions → test-alert → Run workflow. After adding or changing secrets, push any change to `checker.py` (or re-run the latest push run) so the running checker picks them up.

## Run locally

```bash
CALLMEBOT_RECIPIENTS="+19175551234:123456" python3 checker.py            # loop forever, every 5s
python3 checker.py --once                                                # single check
CALLMEBOT_RECIPIENTS="+19175551234:123456" python3 checker.py --test-notify
```

Only the Python standard library is used. Stores and zip codes are set in `STORES` / `QUERY_ZIPS` in `checker.py`.

Note: GitHub pauses scheduled workflows in public repos after 60 days without commits. To resume, click "Enable workflow" in the Actions tab.
