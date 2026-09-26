# GrievEye — Telegram demo

AI-routed grievance redressal. A citizen sends a complaint as text, a voice
note or a photo. Claude extracts the fields and the bot asks only for what is
missing. The case goes to an officer **post** with Accept / Escalate /
Resolved buttons. The officer must send a proof photo, and the **citizen** has
the final word: "No" reopens the case and counts against the officer. A live
web dashboard shows the officer scorecard.

Telegram stands in for WhatsApp in the demo. All rules live in `cases.py`, and
`bot.py` is the only file that knows about Telegram.

## Setup (Windows, once)

```powershell
git clone https://github.com/meet-minimalist/GrievEye.git
cd GrievEye
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env      # then fill it in
python seed_demo.py         # 5 weeks of demo history for the scorecard
```

`.env` settings:

| Setting | What it is |
| --- | --- |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `ANTHROPIC_API_KEY` | Your Claude API key |
| `ANTHROPIC_WORKSPACE_ID` | Only if your key is not scoped to a workspace (Console → Settings → Workspaces) |
| `OFFICER_CHAT_ID` | The Telegram chat that gets cases for every post nobody has claimed. Run `python get_officer_chat_id.py` and message the bot from the officer account |
| `WHISPER_MODEL` | `base` (fast) or `small` (better Kannada). Test both |

If the Claude API is not reachable, the bot still works: a keyword fallback
picks the category, and the citizen confirms with buttons.

## Run

```powershell
.venv\Scripts\python bot.py
```

- Bot: message it from the citizen account.
- Dashboard: open http://localhost:8000 and put it on the projector.

## Dashboards

| View | Who | How to open |
| --- | --- | --- |
| DC / MLA | Collector, MLA | http://localhost:8000 |
| My complaints | Citizen | `/mydashboard` in the citizen bot |
| Officer desk | Officer | `/mydashboard` in the officer bot: queue, overdue cases, own score |
| Senior officer desk | EO, Tahsildar, AEE, EE | Same link: also "Escalated to me", team scorecard, team escalations |
| All views (demo) | You, on the laptop | http://localhost:8000/demo |

Links from `/mydashboard` are private (signed) and use the laptop's Wi-Fi
address, so a phone on the same Wi-Fi can open them. The first time you run
the bot, Windows asks whether Python may use the network: allow **Private
networks**, or phones cannot connect.

## Public link (any network, any phone)

The bot itself needs no public address: it fetches messages from Telegram.
Only the dashboards need one, when phones or laptops are not on the same Wi-Fi.

**Cloudflare tunnel (recommended, no account):**
1. Install once: download
   `https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe`
   and save it as `%LOCALAPPDATA%\cloudflared\cloudflared.exe`.
2. Start the bot, then double-click `start_tunnel.cmd`. Keep its window open.
3. The window prints `https://<words>.trycloudflare.com`: that is the DC page.
   `/mydashboard` links use it automatically. The address changes on every start.

**ngrok (alternative):** needs agent version 3.20 or newer (`winget` installs
an older one; download from ngrok.com). Some antivirus programs (for example
Quick Heal) delete `ngrok.exe`. Then `ngrok http 8000`; links use it automatically.

Through either tunnel, `/demo` and the DC controls stay laptop-only.

## Separate officer bot (recommended)

With one bot, officer alerts arrive in the same chat as citizen messages.
For a clean demo, create a second bot:

1. In Telegram, open @BotFather, send `/newbot`, name it for example "GrievEye Officer".
2. Put its token in `.env` as `OFFICER_BOT_TOKEN=...`.
3. Restart `bot.py`, open the new bot, and press **Start** (a bot cannot message you before that).

The same Telegram account can then be citizen in one chat and officer in the other.

## Demo script (4 minutes)

1. **Citizen:** send a voice note: "Hosahalli-yalli mooru dinadinda neeru illa" (or type "no water in Hosahalli for 3 days").
2. First contact: choose a language, agree to the privacy notice, give a name. Then the complaint is processed.
3. Bot asks for anything missing with buttons, shows a summary, and gives a tracking ID.
4. **Officer phone:** gets the alert with the original voice note. Tap **Accept**, then **Resolved**, and send a photo.
5. **Citizen:** sees the photo. Tap **No**. The case reopens, the officer is alerted, and the PDO row flashes on the dashboard.
6. Do it again and tap **No** a second time: the case goes to the senior officer (EO) automatically.
7. Dashboard: point at the scorecard. AEE, PWD Kanakapura is the weak officer (slow, many reopens).
8. Optional: press **+48 h** on the dashboard (or `/tick48`) to show automatic escalation of a case nobody accepted.

The triage panel at the bottom holds low-confidence cases. Pick a post and press **Send** to route one live.

## Commands

| Command | Who | What |
| --- | --- | --- |
| `/start`, `/language` | Citizen | Start, change language |
| `/status <ID>` | Citizen or officer | Case status and history |
| `/stopdata` | Citizen | Withdraw consent and delete personal details (DPDP) |
| `/mydashboard` | Everyone | Private link to your web view |
| `/officer` | Officer | Claim a post, so its cases come to this account |
| `/mycases` | Officer | Open cases and score |
| `/dashboard` | Anyone | Text summary |
| `/tick48` | Demo | Move the clock 48 hours ahead and apply deadline rules |

With one officer phone, do nothing: every post falls back to `OFFICER_CHAT_ID`.
With two phones, run `/officer` on the second one and claim
"EO, Kanakapura Taluk Panchayat" so escalations visibly go to a different person.

## Files

| File | Job |
| --- | --- |
| `bot.py` | Telegram adapter and entry point; also starts the dashboard |
| `cases.py` | State machine, reopen and escalation rules, deadline sweep, scorecard |
| `classifier.py` | Claude extraction (text and photos) with a keyword fallback |
| `transcribe.py` | Local speech-to-text (faster-whisper) |
| `messages.py` | All citizen text in Kannada and English |
| `officer_directory.py` | Village + category → post, senior posts, target days |
| `database.py` | SQLite tables: citizens, officers, cases, events, settings |
| `dashboard.py` | Web server: DC page, role pages, signed links, photo proxy; `python dashboard.py` runs it alone |
| `dashboard.html`, `citizen.html`, `officer.html`, `demo.html`, `common.css` | The web pages |
| `seed_demo.py` | Demo history. `python seed_demo.py` wipes cases and reseeds |

## Real vs. simplified

**Real:** Telegram messaging, Claude extraction, local voice transcription,
consent gating, proof-photo enforcement, citizen verification, reopen and
2-strike escalation, deadline escalation, audit trail of every change,
scorecard computed from that trail, triage queue.

**Simplified:** 2 villages and 12 posts instead of the full directory; the
demo clock stands in for real waiting; no login on the dashboard; no data
retention job yet; Telegram instead of the WhatsApp Business API.
