# How GrievEye works

GrievEye lets a villager raise a complaint by sending a message, a voice note or a photo to a bot. The bot works out what the problem is and where it is, sends it to the officer responsible, and keeps the case open until the citizen says it is actually fixed. Every step is logged, so the DC can see which officers solve problems and which ones only close files.

For the hackathon it runs on Telegram. WhatsApp would replace only the messaging layer; the rules stay the same.

## The process

**1. The citizen complains.** First contact asks for a language (Kannada or English), shows a short privacy notice, and asks for a name. After that the citizen just describes the problem, in any form.

**2. The bot fills in the gaps.** It needs three things: the village, the type of problem, and for problems at a physical spot, a location. Whatever it can't work out from the message, it asks for, with buttons. The citizen can always type instead, say "not sure", or skip. It then shows a summary and waits for "Correct".

**3. The case is routed to a post, not a person.** Village + type decide the post (for example, water in Hosahalli goes to the PDO, Hosahalli GP). The citizen gets a tracking ID. If the bot isn't confident, or the village is unknown, the case goes to the duty officer instead, who picks the right post with one tap.

**4. The officer acts.** The alert has the complaint, the original voice note or photo, and a map link. The officer can:

- **Accept** the case
- **Escalate** it to their senior, giving a reason
- **Assign** it down to their own staff (a PDO to a waterman, an AE to a lineman)
- **Resolve** it, by sending a photo as proof (or resolving without one, which gets flagged)

After resolving, the officer can share their location. The system records how far they were from the complaint.

**5. The citizen has the final word.** They get the proof photo and either rate the officer from 1 to 5, which closes the case, or tap "Not fixed", which reopens it. A second "Not fixed" sends the case to the senior officer automatically.

**Time rules.** If nobody accepts a case within 48 hours, it moves up the chain on its own. If the citizen never replies after a resolution, the case closes as "unconfirmed" after 7 days and counts for less.

## Who sees what

| Person | Where | What they see |
|---|---|---|
| Citizen | Telegram, plus a personal web page | Their own complaints, status, history, proof photos |
| Field staff / officer | Telegram alerts, plus an officer desk page | Their queue, overdue cases, their score and how it's made up |
| Senior officer | Same desk page | Also: cases escalated to them, their team's scores, who escalated what |
| DC / MLA | The main dashboard | Every post's score, live activity, cases by type, the triage queue |

Anyone gets their personal page link by sending `/mydashboard` to the bot. Links are signed, so one person can't open another person's page.

## The score

Each officer gets a score out of 100, shown only after 10 closed cases:

- 35%: cases the citizen confirmed as fixed
- 25%: speed, measured against a target for that type of problem
- 20%: few reopens
- 10%: citizen rating
- 10%: accepting within 48 hours

Escalating for a genuine reason ("outside my powers") and assigning work down are never penalised. Escalations caused by delay or by repeated reopens are.

## Under the hood

Everything runs as one Python process on a laptop: the Telegram bot and a small web server for the dashboards.

```
Citizen ─► citizen bot ─► speech-to-text / AI / keywords ─► case rules ─► SQLite
                                                                │
Officer ◄── officer bot ◄────────── alerts ◄────────────────────┘
                                                                │
DC, officers, citizens ◄── web dashboards ◄─────────────────────┘
```

**Understanding the message.** Voice notes are transcribed on the laptop with Whisper, so nothing is sent out for that. The text (and any photo) goes to Claude Haiku, which returns the village, type, a summary in both languages, a confidence score, and a flag for sensitive cases. If the AI isn't available, a keyword list in English, Kannada, and Kannada typed in English letters ("neeru illa") does a simpler job.

**Location.** Telegram strips GPS from normal photos, so the bot asks for a one-tap location pin. Photos sent "as a file" keep their GPS data, and the bot reads it automatically, for citizens and for officers' proof photos.

**The rules** live in one file (`cases.py`) as a state machine. A case can only move along allowed paths (for example, only the citizen can mark it fixed). Every move is written to an `events` table, and the scores are calculated from that log, not from anything that can be edited by hand.

**Two bots or one.** With a second bot token, officers get their own chat, separate from citizens. Media is copied between the bots, because a Telegram file ID only works in the bot that received it. With one bot, both roles share it.

**Dashboards.** They are plain HTML pages that refresh every few seconds. On the same Wi-Fi, they are reachable at the laptop's IP address. Anywhere else, `start_tunnel.cmd` opens a Cloudflare tunnel with a public https address. The demo page and the DC's controls only work from the laptop itself, never through the tunnel.

**Privacy.** Nothing is stored before the citizen agrees. Officers see only the citizen's first name. Sensitive cases are hidden from the dashboards' lists. `/stopdata` removes a citizen's personal details and keeps only anonymous numbers.

## Main files

| File | What it does |
|---|---|
| `bot.py` | Telegram side: conversations, buttons, alerts |
| `cases.py` | Case rules, deadlines, escalation, scores |
| `classifier.py` | AI and keyword understanding of complaints |
| `transcribe.py` | Voice to text |
| `geo.py` | GPS from photos, distances, map links |
| `officer_directory.py` | Villages, problem types, posts and who reports to whom |
| `database.py` | SQLite storage |
| `dashboard.py` + `*.html` | Web pages and private links |
| `messages.py` | Everything the citizen reads, in Kannada and English |

## Running it

```
.venv\Scripts\python seed_demo.py    # optional: 5 weeks of sample history
.venv\Scripts\python bot.py          # bot + dashboards on port 8000
start_tunnel.cmd                     # optional: public link
```

Settings live in `.env`: bot tokens, the Claude API key, and the fallback officer chat. The README covers setup.

## What's simplified for now

- Two villages and about twenty posts, not the full district directory
- Telegram instead of the WhatsApp Business API
- A demo clock (`/tick48`) stands in for real waiting
- No login on the DC dashboard, and no automatic data deletion job yet
- Runs on a laptop; a pilot would need a proper server in an Indian region
