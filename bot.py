"""
GrievEye Telegram bot — entry point.

    python bot.py

Starts the Telegram bot and the dashboard (http://localhost:8000) in one process.
This file is the Telegram "channel adapter": it turns Telegram updates into calls
on cases.py and turns results into messages. The rules live in cases.py.
"""
import asyncio
import difflib
import logging
import os
import sys
import tempfile
import time

from dotenv import load_dotenv

load_dotenv()
# Windows consoles default to a legacy code page; Kannada in the logs would crash printing.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from telegram import (  # noqa: E402
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove,
    Update,
)
from telegram.ext import (  # noqa: E402
    ApplicationBuilder, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, TypeHandler,
    filters,
)

import cases  # noqa: E402
import dashboard  # noqa: E402
import geo  # noqa: E402
import database as db  # noqa: E402
from classifier import classify_complaint, infer_category, keyword_fallback  # noqa: E402
from messages import STATUS_LABEL, t  # noqa: E402
from officer_directory import (  # noqa: E402
    ALL_POSTS, CATEGORIES, CATEGORY_KN, DEFAULT_POST, VILLAGES, VILLAGE_KN, get_officer_post, get_senior_post,
    get_team,
)

logging.basicConfig(format="%(asctime)s %(levelname)s %(message)s", level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("grieveye")

DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", 8000))
MAX_QUESTIONS = 3
NOT_SURE = "?"

APP = None          # the citizen bot; set in main()
OFFICER_APP = None  # the officer bot, when OFFICER_BOT_TOKEN is set; else officers use APP
LOOP = None   # the bot's event loop, for scheduling from the dashboard thread


# ---------- helpers ----------

def kb(rows):
    return InlineKeyboardMarkup([[InlineKeyboardButton(text, callback_data=data) for text, data in row]
                                 for row in rows])


def lang_of(chat_id):
    citizen = db.get_citizen(chat_id)
    return (citizen or {}).get("language") or "kn"


officer_chat = cases.officer_chat


# Problems at a physical spot: the officer needs to find it, so the bot asks for a location pin.
PHYSICAL = {"Water Supply", "Electricity", "Roads", "Sanitation", "Stray Animals"}


def location_keyboard(share_label, skip_label):
    """A phone keyboard with a one-tap "send my location" button (mobile Telegram only)."""
    return ReplyKeyboardMarkup([[KeyboardButton(share_label, request_location=True)], [KeyboardButton(skip_label)]],
                               resize_keyboard=True, one_time_keyboard=True)


def officer_bot():
    """The bot that talks to officers: the separate officer bot if there is one."""
    return (OFFICER_APP or APP).bot


async def copy_media(file_id, from_bot):
    """Telegram file_ids only work in the bot that received the file, so between two
    bots we copy the bytes instead."""
    tg_file = await from_bot.get_file(file_id)
    return bytes(await tg_file.download_as_bytearray())


def village_label(v, lang):
    return VILLAGE_KN.get(v, v) if lang == "kn" else v


def category_label(c, lang):
    return CATEGORY_KN.get(c, c) if lang == "kn" else c


def fmt_time(ts):
    return time.strftime("%d %b %H:%M", time.localtime(ts))


# ---------- officer notifications ----------

async def alert_officer(case, header="🆕 New case"):
    chat = officer_chat(case["officer_post"])
    if not chat:
        log.warning("No chat for post %s; set OFFICER_CHAT_ID or run /officer", case["officer_post"])
        return
    bot = officer_bot()
    first_name = (case["citizen_name"] or "Citizen").split()[0]
    lines = [
        f"{header}: {case['tracking_id']}",
        f"👤 For: {case['officer_post']}",
        f"📍 Village: {case['village'] or 'Unknown'}",
        f"📂 Category: {case['category'] or 'Unknown'}",
        f"📝 Issue: {case['description']}",
        f"🙋 Citizen: {first_name}",
    ]
    if case["lat"] is not None:
        lines.append(f"🗺 Location: {geo.maps_link(case['lat'], case['lon'])}")
    if case["restricted"]:
        lines.append("🔒 Restricted case: do not share.")
    if case["reopen_count"]:
        lines.append(f"🔁 Reopened {case['reopen_count']} time(s) by the citizen")
    try:
        media = case["media_file_id"]
        if media and OFFICER_APP:
            media = await copy_media(media, APP.bot)
        if case["media_type"] == "voice" and media:
            await bot.send_voice(chat, media, caption=f"Original voice note · {case['tracking_id']}")
        elif case["media_type"] == "photo" and media:
            await bot.send_photo(chat, media, caption=f"Citizen's photo · {case['tracking_id']}")
    except Exception as exc:
        log.warning("Could not forward media: %s", exc)
    await bot.send_message(chat, "\n".join(lines), reply_markup=officer_buttons(case))


async def alert_triage(case):
    """A case the AI could not route goes to the duty officer, who picks the right post."""
    chat = officer_chat(DEFAULT_POST)
    if not chat:
        return
    tid = case["tracking_id"]
    text = (f"🟡 Needs routing: {tid}\n"
            f"📍 Village: {case['village'] or 'Not given'}\n"
            f"📂 Category: {case['category'] or 'Not given'}\n"
            f"📝 Issue: {case['description']}\n\n"
            "The AI could not decide who handles this. Tap the post to send it to:")
    rows = [[(p, f"tr:{tid}:{i}")] for i, p in enumerate(ALL_POSTS)]
    await officer_bot().send_message(chat, text, reply_markup=kb(rows))


async def on_triage_route(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, tid, i = q.data.split(":")
    post = ALL_POSTS[int(i)]
    try:
        case = cases.route_triage(tid, post)
    except cases.InvalidTransition:
        await q.answer("Already routed", show_alert=True)
        await q.edit_message_reply_markup(None)
        return
    await q.answer("Sent")
    await q.edit_message_text(q.message.text.split("\n\nThe AI")[0] + f"\n\n➡️ Sent to {post}.")
    await alert_officer(case)
    await tell_citizen(case, "routed")


def officer_buttons(case, accepted=False):
    """Buttons under an officer's case message. Officers with posts below them can assign down."""
    tid = case["tracking_id"]
    first = ("📷 Resolved (send proof)", f"o:res:{tid}") if accepted else ("✅ Accept", f"o:acc:{tid}")
    rows = [[first, ("⬆️ Escalate", f"o:esc:{tid}")]]
    if get_team(case["officer_post"]):
        rows.append([("⬇️ Assign to my team", f"o:dlg:{tid}")])
    return kb(rows)


async def tell_citizen(case, key, **kwargs):
    if case["is_seed"]:
        return  # seed cases have no real citizen chat
    lang = lang_of(case["citizen_chat_id"])
    await APP.bot.send_message(case["citizen_chat_id"], t(lang, key, tid=case["tracking_id"],
                                                          post=case["officer_post"], **kwargs))


async def announce_escalation(case):
    await alert_officer(case, header="⬆️ Escalated case")
    await tell_citizen(case, "escalated")


async def announce_sweep(results):
    for kind, case in results:
        if kind == "escalated":
            await announce_escalation(case)


# ---------- citizen onboarding ----------

async def ask_language(chat_id, context):
    await context.bot.send_message(chat_id, t("kn", "choose_language"), reply_markup=kb([
        [("ಕನ್ನಡ", "lang:kn"), ("English", "lang:en")],
    ]))


async def ask_consent(chat_id, context, lang):
    await context.bot.send_message(chat_id, t(lang, "privacy_notice"), reply_markup=kb([
        [(t(lang, "agree"), "consent:yes"), (t(lang, "disagree"), "consent:no")],
    ]))


async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE, item) -> bool:
    """Make sure the citizen has chosen a language, consented, and given a name.
    If not, keep their message and start onboarding. Returns True when ready."""
    chat_id = update.effective_chat.id
    citizen = db.get_citizen(chat_id)
    if not citizen or not citizen.get("consent_at"):
        if item:
            context.user_data["pending_item"] = item
        if not citizen:
            await ask_language(chat_id, context)
        else:
            await ask_consent(chat_id, context, citizen["language"])
        return False
    if not citizen.get("name"):
        if item:
            context.user_data["pending_item"] = item
        await context.bot.send_message(chat_id, t(citizen["language"], "ask_name"))
        context.user_data["stage"] = "await_name"
        return False
    return True


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    citizen = db.get_citizen(update.effective_chat.id)
    if citizen and citizen.get("consent_at") and citizen.get("name"):
        await update.message.reply_text(t(citizen["language"], "ready", name=citizen["name"]))
    else:
        await ask_language(update.effective_chat.id, context)


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await ask_language(update.effective_chat.id, context)


async def on_language(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = q.data.split(":")[1]
    chat_id = q.message.chat_id
    db.upsert_citizen(chat_id, language=lang)
    await q.edit_message_reply_markup(None)
    citizen = db.get_citizen(chat_id)
    if not citizen.get("consent_at"):
        await ask_consent(chat_id, context, lang)
    elif citizen.get("name"):
        await context.bot.send_message(chat_id, t(lang, "ready", name=citizen["name"]))


async def on_consent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    lang = lang_of(chat_id)
    await q.edit_message_reply_markup(None)
    if q.data == "consent:no":
        context.user_data.clear()
        await context.bot.send_message(chat_id, t(lang, "no_consent"))
        return
    db.upsert_citizen(chat_id, consent_at=time.time(), withdrawn_at=None)
    if not db.get_citizen(chat_id).get("name"):
        context.user_data["stage"] = "await_name"
        await context.bot.send_message(chat_id, t(lang, "ask_name"))
    else:
        await resume_pending(update, context)


async def resume_pending(update, context):
    chat_id = update.effective_chat.id
    item = context.user_data.pop("pending_item", None)
    if item:
        await intake(update, context, item)
    else:
        citizen = db.get_citizen(chat_id)
        await context.bot.send_message(chat_id, t(citizen["language"], "ready", name=citizen["name"]))


# ---------- incoming messages ----------

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    text = update.message.text.strip()

    pending_proof = db.get_setting(f"proof:{chat_id}")
    if pending_proof:
        await remind_proof(update, pending_proof)
        return
    if not OFFICER_APP and await skip_officer_location(update, context):
        return

    draft = context.user_data.get("draft")
    if draft and draft.get("asking") and len(text) <= (120 if draft["asking"] == "location" else 60):
        await typed_field(chat_id, context, draft, text)
        return

    if context.user_data.get("stage") == "await_name":
        context.user_data["stage"] = None
        db.upsert_citizen(chat_id, name=text[:60])
        await resume_pending(update, context)
        return

    item = {"kind": "text", "text": text}
    if await gate(update, context, item):
        await intake(update, context, item)


async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    voice = update.message.voice or update.message.audio
    item = {"kind": "voice", "file_id": voice.file_id}
    if await gate(update, context, item):
        await intake(update, context, item)


def image_file_id(message):
    """A photo, or an image sent as a file (Telegram Desktop, or "send as file")."""
    if message.photo:
        return message.photo[-1].file_id
    if message.document and (message.document.mime_type or "").startswith("image/"):
        return message.document.file_id
    return None


async def handle_officer_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Treat a photo from an officer as proof. Returns False if it is not an officer's proof."""
    chat_id = update.effective_chat.id
    photo_id = image_file_id(update.message)
    tid = db.pop_setting(f"proof:{chat_id}")
    if tid:
        await officer_proof(chat_id, context.bot, tid, photo_id)
        return True
    held = cases.posts_held_by(chat_id)
    accepted = [c for c in db.cases_for_posts(held) if c["status"] == "ACCEPTED"] if held else []
    if not accepted:
        return False
    # The officer sent a photo without tapping Resolved first: ask which case it proves.
    db.set_setting(f"photo:{chat_id}", photo_id)
    rows = [[(f"{c['tracking_id']} · {c['category'] or '?'}, {c['village'] or '?'}", f"pf:{c['tracking_id']}")]
            for c in accepted[-6:]]
    await update.message.reply_text("📷 Which case does this photo prove fixed?", reply_markup=kb(rows))
    return True


async def on_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_id = image_file_id(update.message)
    if not OFFICER_APP and await handle_officer_photo(update, context):
        return

    item = {"kind": "photo", "file_id": photo_id, "text": update.message.caption or ""}
    if await gate(update, context, item):
        await intake(update, context, item)


async def intake(update: Update, context: ContextTypes.DEFAULT_TYPE, item):
    """Turn one citizen message into a draft case, then ask for what is missing."""
    chat_id = update.effective_chat.id
    lang = lang_of(chat_id)
    bot = context.bot
    await bot.send_message(chat_id, t(lang, "processing"))

    text = item.get("text", "")
    image_bytes = None
    try:
        if item["kind"] == "voice":
            from transcribe import transcribe_voice  # loaded lazily: the model is slow to import
            tg_file = await bot.get_file(item["file_id"])
            with tempfile.TemporaryDirectory() as tmp:
                path = os.path.join(tmp, "voice.ogg")
                await tg_file.download_to_drive(path)
                text = await asyncio.to_thread(transcribe_voice, path)
            if not text:
                await bot.send_message(chat_id, t(lang, "voice_failed"))
                return
            await bot.send_message(chat_id, t(lang, "heard", text=text))
        elif item["kind"] == "photo":
            tg_file = await bot.get_file(item["file_id"])
            image_bytes = bytes(await tg_file.download_as_bytearray())
    except Exception:
        log.exception("Media download or transcription failed")
        await bot.send_message(chat_id, t(lang, "voice_failed"))
        return

    result = await asyncio.to_thread(classify_complaint, text, image_bytes)
    log.info("Classified %s: %s", chat_id, result)

    if not result.get("is_grievance") and item["kind"] != "photo":
        await bot.send_message(chat_id, t(lang, "not_grievance"))
        return

    confidence = result.get("confidence", 0)
    if not result.get("category"):
        guessed = infer_category(f"{text} {result.get('summary_en') or ''}")
        if guessed:
            result["category"] = guessed
            confidence = max(confidence, 0.65)

    # Photos sent "as a file" keep their GPS metadata; normal photos do not.
    gps = geo.exif_gps(image_bytes) if image_bytes else None
    early_pin = context.user_data.pop("pending_location", None)
    location = gps or early_pin

    context.user_data["draft"] = {
        "lat": location[0] if location else None,
        "lon": location[1] if location else None,
        "location_source": "photo" if gps else "pin" if early_pin else None,
        "raw_text": text,
        "media_type": item["kind"] if item["kind"] in ("voice", "photo") else None,
        "media_file_id": item.get("file_id"),
        "village": result.get("village"),
        "category": result.get("category"),
        "summary_en": result.get("summary_en") or text[:200],
        "summary_kn": result.get("summary_kn"),
        "confidence": confidence,
        "sensitive": result.get("sensitive", False),
        "questions": 0,
        "citizen_picked": False,
    }
    await ask_next(chat_id, context)


async def ask_next(chat_id, context):
    """Ask for the next missing field with buttons, or show the summary to confirm."""
    draft = context.user_data.get("draft")
    lang = lang_of(chat_id)
    bot = context.bot

    missing = [f for f in ("village", "category") if not draft.get(f)]
    if missing and draft["questions"] >= MAX_QUESTIONS:
        for f in missing:  # too many questions: let a human sort it out
            draft[f] = NOT_SURE
        missing = []

    if "village" in missing:
        draft["questions"] += 1
        draft["asking"] = "village"
        rows = [[(village_label(v, lang), f"vil:{i}")] for i, v in enumerate(VILLAGES)]
        rows.append([(t(lang, "not_sure"), "vil:x")])
        await bot.send_message(chat_id, t(lang, "ask_village"), reply_markup=kb(rows))
        return
    if "category" in missing:
        draft["questions"] += 1
        draft["asking"] = "category"
        buttons = [(category_label(c, lang), f"cat:{i}") for i, c in enumerate(CATEGORIES)]
        rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
        rows.append([(t(lang, "not_sure"), "cat:x")])
        await bot.send_message(chat_id, t(lang, "ask_category"), reply_markup=kb(rows))
        return

    if (draft.get("lat") is None and not draft.get("location_asked")
            and draft["category"] in PHYSICAL and not draft.get("landmark")):
        draft["location_asked"] = True
        draft["asking"] = "location"
        await bot.send_message(chat_id, t(lang, "ask_location"),
                               reply_markup=location_keyboard(t(lang, "share_location"), t(lang, "skip")))
        return

    draft["asking"] = None
    village, category = draft["village"], draft["category"]
    routable = NOT_SURE not in (village, category) and not draft.get("typed_village")
    post = get_officer_post(village, category) if routable else t(lang, "post_triage")
    summary = draft["summary_kn"] if lang == "kn" and draft["summary_kn"] else draft["summary_en"]
    await bot.send_message(chat_id, t(
        lang, "confirm",
        village=t(lang, "not_sure") if village == NOT_SURE else village_label(village, lang),
        category=t(lang, "not_sure") if category == NOT_SURE else category_label(category, lang),
        summary=summary, post=post,
        location=(t(lang, "loc_photo") if draft.get("location_source") == "photo"
                  else t(lang, "loc_pin") if draft.get("lat") is not None
                  else draft.get("landmark") or t(lang, "loc_none")),
    ), reply_markup=kb([[(t(lang, "correct"), "cf:yes"), (t(lang, "edit"), "cf:edit")]]))


def match_one(text, options, labels):
    """Match typed text to an option: exact, Kannada name, then a close spelling."""
    low = text.strip().lower()
    for o in options:
        if low in (o.lower(), labels.get(o, "").lower()):
            return o
    names = {o.lower(): o for o in options}
    names.update({labels[o].lower(): o for o in options if o in labels})
    close = difflib.get_close_matches(low, list(names), n=1, cutoff=0.75)
    return names[close[0]] if close else None


async def typed_field(chat_id, context, draft, text):
    """The citizen typed an answer instead of tapping a button."""
    field = draft["asking"]
    draft["asking"] = None
    if field == "location":
        if text not in (t("kn", "skip"), t("en", "skip")):
            draft["landmark"] = text.strip()[:80]
        await context.bot.send_message(chat_id, "👍", reply_markup=ReplyKeyboardRemove())
        await ask_next(chat_id, context)
        return
    if field == "village":
        match = match_one(text, VILLAGES, VILLAGE_KN)
        if not match:  # "near the school, Hosahalli cross": a known village inside a landmark
            low = text.lower()
            match = next((v for v in VILLAGES if v.lower() in low or VILLAGE_KN[v] in text), None)
            if match:
                draft["landmark"] = text.strip()[:80]
        # A village we do not know yet is kept as typed; triage finds the right officer.
        draft["village"] = match or text.strip()[:40]
        draft["typed_village"] = match is None
    else:
        match = match_one(text, CATEGORIES, CATEGORY_KN) or keyword_fallback(text)["category"]
        draft["category"] = match or "Other"
        draft["citizen_picked"] = True
        draft["category_note"] = None if match else text.strip()[:60]
    await ask_next(chat_id, context)


async def officer_location(chat_id, bot, lat, lon) -> bool:
    """A pin from an officer who just resolved a case. Returns False if none was expected."""
    tid = db.pop_setting(f"proofloc:{chat_id}")
    if not tid:
        return False
    distance = cases.set_proof_location(tid, lat, lon)
    text = f"📍 Location saved for {tid}"
    text += f": {geo.describe_distance(distance)}" if distance is not None else "."
    await bot.send_message(chat_id, text, reply_markup=ReplyKeyboardRemove())
    return True


async def on_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    loc = update.message.location
    if not OFFICER_APP and await officer_location(chat_id, context.bot, loc.latitude, loc.longitude):
        return
    lang = lang_of(chat_id)
    draft = context.user_data.get("draft")
    if draft:
        draft.update(lat=loc.latitude, lon=loc.longitude, location_source="pin", location_asked=True, asking=None)
        await update.message.reply_text(t(lang, "loc_saved"), reply_markup=ReplyKeyboardRemove())
        await ask_next(chat_id, context)
    else:  # a pin before the complaint: keep it for the next one
        context.user_data["pending_location"] = (loc.latitude, loc.longitude)
        await update.message.reply_text(t(lang, "loc_first"), reply_markup=ReplyKeyboardRemove())


async def officer_location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.location
    if not await officer_location(update.effective_chat.id, context.bot, loc.latitude, loc.longitude):
        await update.message.reply_text("Location is only needed after you resolve a case.")


async def skip_officer_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.message.text.strip() == "Skip" and db.pop_setting(f"proofloc:{update.effective_chat.id}"):
        await update.message.reply_text("OK, no location.", reply_markup=ReplyKeyboardRemove())
        return True
    return False


async def on_draft_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    chat_id = q.message.chat_id
    draft = context.user_data.get("draft")
    await q.edit_message_reply_markup(None)
    if not draft:
        return  # stale button from an earlier complaint
    kind, value = q.data.split(":")
    draft["asking"] = None

    lang = lang_of(chat_id)
    if value == "x":  # "Not sure": let the citizen describe it in their own words
        draft["asking"] = "village" if kind == "vil" else "category"
        key = "describe_village" if kind == "vil" else "describe_category"
        await context.bot.send_message(chat_id, t(lang, key),
                                       reply_markup=kb([[(t(lang, "skip"), f"{kind}:skip")]]))
        return
    if kind == "vil":
        draft["typed_village"] = False
        draft["village"] = NOT_SURE if value == "skip" else VILLAGES[int(value)]
    elif kind == "cat":
        draft["category"] = NOT_SURE if value == "skip" else CATEGORIES[int(value)]
        draft["citizen_picked"] = value != "skip"
    elif kind == "cf" and value == "edit":
        draft.update(village=None, category=None, questions=0, typed_village=False, category_note=None,
                     landmark=None, location_asked=draft.get("lat") is not None)
    elif kind == "cf" and value == "yes":
        if draft.get("village") and draft.get("category"):
            await file_case(chat_id, context)
            return
        # An older confirm button, tapped while a newer complaint is still missing details.
    await ask_next(chat_id, context)


async def file_case(chat_id, context):
    draft = context.user_data.pop("draft")
    citizen = db.get_citizen(chat_id)
    lang = citizen["language"]

    confidence = draft["confidence"]
    if draft["citizen_picked"]:
        confidence = max(confidence, 0.9)
    if NOT_SURE in (draft["village"], draft["category"]) or draft.get("typed_village"):
        confidence = 0.0
    description = draft["summary_en"]
    if draft.get("category_note"):
        description += f" (type given by citizen: {draft['category_note']})"
    if draft.get("landmark"):
        description += f" (location: {draft['landmark']})"

    case = cases.create_case(
        citizen_chat_id=chat_id,
        citizen_name=citizen["name"],
        village=None if draft["village"] == NOT_SURE else draft["village"],
        category=None if draft["category"] == NOT_SURE else draft["category"],
        description=description,
        raw_text=draft["raw_text"],
        media_type=draft["media_type"],
        media_file_id=draft["media_file_id"],
        confidence=confidence,
        restricted=draft["sensitive"],
        lat=draft.get("lat"),
        lon=draft.get("lon"),
        location_source=draft.get("location_source"),
    )
    if case["status"] == "TRIAGE":
        await context.bot.send_message(chat_id, t(lang, "filed_triage", tid=case["tracking_id"]))
        await alert_triage(case)
    else:
        await context.bot.send_message(chat_id, t(lang, "filed", tid=case["tracking_id"],
                                                  post=case["officer_post"]))
        await alert_officer(case)


# ---------- officer actions ----------

async def on_officer_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    parts = q.data.split(":")
    action, tid = parts[1], parts[2]
    case = db.get_case(tid)
    chat_id = q.message.chat_id

    if not case:
        await q.answer("Case not found")
        return
    if officer_chat(case["officer_post"]) != chat_id:
        await q.answer(f"This case is now with {case['officer_post']}", show_alert=True)
        await q.edit_message_reply_markup(None)
        return

    try:
        if action == "acc":
            case = cases.accept(tid)
            await q.answer("Accepted")
            await q.edit_message_text(q.message.text + "\n\n✅ You accepted this case.",
                                      reply_markup=officer_buttons(case, accepted=True))
            await tell_citizen(case, "accepted")

        elif action == "dlg":
            team = get_team(case["officer_post"])
            await q.answer()
            rows = [[(p, f"o:dt:{tid}:{ALL_POSTS.index(p)}")] for p in team]
            rows.append([("↩ Back", f"o:back:{tid}")])
            await q.edit_message_reply_markup(kb(rows))

        elif action == "dt":
            to_post = ALL_POSTS[int(parts[3])]
            by = case["officer_post"]
            case = cases.assign_down(tid, to_post)
            await q.answer("Assigned")
            await q.edit_message_text(q.message.text + f"\n\n⬇️ You assigned this to {to_post}.")
            await alert_officer(case, header=f"📌 Assigned to you by {by}")
            await tell_citizen(case, "assigned")

        elif action == "back":
            await q.answer()
            await q.edit_message_reply_markup(officer_buttons(case, accepted=case["status"] == "ACCEPTED"))

        elif action == "esc":
            await q.answer()
            await q.edit_message_reply_markup(kb([
                [("Outside my powers", f"o:er:{tid}:outside_powers")],
                [("Needs senior approval", f"o:er:{tid}:needs_approval")],
            ]))

        elif action == "er":
            reason = parts[3]
            escalated = cases.escalate(tid, reason)
            if not escalated:
                await q.answer("There is no senior post above yours.", show_alert=True)
                return
            await q.answer("Escalated")
            await q.edit_message_text(q.message.text + f"\n\n⬆️ Escalated to {escalated['officer_post']}.")
            await announce_escalation(escalated)

        elif action == "res":
            if case["status"] != "ACCEPTED":
                raise cases.InvalidTransition(case["status"])
            db.set_setting(f"proof:{chat_id}", tid)
            await q.answer()
            await q.edit_message_reply_markup(None)
            await context.bot.send_message(
                chat_id,
                f"📷 Send ONE PHOTO that shows {tid} is fixed (📎 → Gallery or Camera).\n"
                "The citizen is told as soon as the photo arrives.\n\n"
                "No photo? Tap “Resolve without photo”. It is marked as “no proof” on the dashboard.",
                reply_markup=proof_buttons(tid))

        elif action == "nophoto":
            db.pop_setting(f"proof:{chat_id}")
            await q.answer()
            await q.edit_message_reply_markup(None)
            await officer_proof(chat_id, context.bot, tid, None)

        elif action == "cancel":
            db.pop_setting(f"proof:{chat_id}")
            await q.answer("Cancelled")
            await q.edit_message_text(f"{tid}: not resolved yet.", reply_markup=officer_buttons(case, accepted=True))

    except cases.InvalidTransition:
        await q.answer(f"Not possible now: case is {case['status']}", show_alert=True)
        await q.edit_message_reply_markup(None)


PROOF_REMINDER = "📷 {tid} is waiting for a proof PHOTO (📎 → Gallery or Camera)."


def proof_buttons(tid):
    return kb([[("✅ Resolve without photo", f"o:nophoto:{tid}")], [("✖ Cancel", f"o:cancel:{tid}")]])


async def remind_proof(update, tid):
    await update.message.reply_text(PROOF_REMINDER.format(tid=tid), reply_markup=proof_buttons(tid))


async def officer_proof(chat_id, bot, tid, photo_id):
    """Mark a case resolved (with the officer's photo, or without one), and tell the citizen."""
    case = db.get_case(tid)
    if not case or case["status"] != "ACCEPTED":
        await bot.send_message(chat_id, f"Could not mark {tid} resolved: it is {case and case['status']}.")
        return
    if case["is_seed"]:  # demo history: no real citizen to ask
        cases.resolve(tid, photo_id, allow_no_proof=True)
        await bot.send_message(chat_id, f"✅ {tid} marked resolved (demo case, no citizen to ask).")
        return
    citizen = case["citizen_chat_id"]
    lang = lang_of(citizen)
    gps = None
    if photo_id:
        # Copy the bytes: works across two bots and for images sent as files. The file_id the
        # citizen bot gets back is stored, so the citizen's web page can show the photo too.
        photo = await copy_media(photo_id, bot)
        gps = geo.exif_gps(photo)
        sent = await APP.bot.send_photo(citizen, photo,
                                        caption=t(lang, "resolved", tid=tid, post=case["officer_post"]))
        case = cases.resolve(tid, sent.photo[-1].file_id)
    else:
        await APP.bot.send_message(citizen, t(lang, "resolved_noproof", tid=tid, post=case["officer_post"]))
        case = cases.resolve(tid, None, allow_no_proof=True)
    await bot.send_message(chat_id, f"✅ {tid} marked resolved. The citizen has been told and asked "
                                    "to rate you or reopen the case.")
    await ask_citizen_verdict(case)
    if gps:
        distance = cases.set_proof_location(tid, *gps)
        await bot.send_message(chat_id, "📍 Photo location saved" +
                               (f": {geo.describe_distance(distance)}" if distance is not None else "."))
    else:
        db.set_setting(f"proofloc:{chat_id}", tid)
        await bot.send_message(chat_id, f"📍 Optional: share your location now to show you were on site for {tid}.",
                               reply_markup=location_keyboard("📍 Share my location", "Skip"))


async def ask_citizen_verdict(case):
    """One message: rate 1-5 (fixed, closes the case) or reopen (not fixed)."""
    tid = case["tracking_id"]
    lang = lang_of(case["citizen_chat_id"])
    await APP.bot.send_message(case["citizen_chat_id"], t(lang, "verify", tid=tid), reply_markup=kb([
        [(f"{n}⭐", f"cr:{n}:{tid}") for n in range(1, 6)],
        [(t(lang, "reopen_btn"), f"cv:no:{tid}")],
    ]))


async def on_proof_pick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The officer sent a photo first, then picked which case it proves."""
    q = update.callback_query
    tid = q.data.split(":")[1]
    chat_id = q.message.chat_id
    photo_id = db.pop_setting(f"photo:{chat_id}")
    await q.answer()
    await q.edit_message_reply_markup(None)
    if not photo_id:
        await context.bot.send_message(chat_id, "Please send the photo again.")
        return
    case = db.get_case(tid)
    if not case or officer_chat(case["officer_post"]) != chat_id:
        await context.bot.send_message(chat_id, "This case is not with you.")
        return
    await officer_proof(chat_id, context.bot, tid, photo_id)


# ---------- citizen verification ----------

async def on_close_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The citizen rated the officer: the problem is fixed, the case closes."""
    q = update.callback_query
    _, n, tid = q.data.split(":")
    case = db.get_case(tid)
    if not case or case["citizen_chat_id"] != q.message.chat_id:
        await q.answer("Not your case")
        return
    try:
        case, _ = cases.citizen_verdict(tid, "yes")
    except cases.InvalidTransition:
        await q.answer("Already answered")
        await q.edit_message_reply_markup(None)
        return
    cases.rate(tid, int(n))
    await q.answer()
    lang = lang_of(q.message.chat_id)
    await q.edit_message_text(q.message.text + f"\n\n→ {'⭐' * int(n)}")
    await context.bot.send_message(q.message.chat_id, t(lang, "thanks_verified", tid=tid))
    chat = officer_chat(case["officer_post"])
    if chat:
        await officer_bot().send_message(chat, f"🎉 Citizen confirmed {tid} is fixed and rated you "
                                               f"{'⭐' * int(n)} ({n}/5). Case closed.")


async def on_verdict(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """The citizen says it is not fixed: reopen (the second time, escalate)."""
    q = update.callback_query
    _, answer, tid = q.data.split(":")
    case = db.get_case(tid)
    if not case or case["citizen_chat_id"] != q.message.chat_id:
        await q.answer("Not your case")
        return
    try:
        case, outcome = cases.citizen_verdict(tid, answer)
    except cases.InvalidTransition:
        await q.answer("Already answered")
        await q.edit_message_reply_markup(None)
        return
    await q.answer()
    lang = lang_of(case["citizen_chat_id"])
    await q.edit_message_text(q.message.text + f"\n\n→ {t(lang, 'reopen_btn')}")

    if outcome == "verified":
        await context.bot.send_message(q.message.chat_id, t(lang, "thanks_verified", tid=tid))
    elif outcome == "reopened":
        await context.bot.send_message(q.message.chat_id, t(lang, "thanks_reopened", tid=tid))
        await alert_officer(case, header=f"🔁 Citizen says NOT fixed ({case['reopen_count']} of "
                                         f"{cases.MAX_REOPENS})")
    else:
        await context.bot.send_message(q.message.chat_id, t(lang, "thanks_escalated", tid=tid,
                                                            post=case["officer_post"]))
        await alert_officer(case, header="⬆️ Escalated: citizen said not fixed twice")


async def on_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Rating buttons from messages sent before the rate-or-reopen change."""
    q = update.callback_query
    _, n, tid = q.data.split(":")
    case = db.get_case(tid)
    if not case or case["citizen_chat_id"] != q.message.chat_id:
        await q.answer()
        return
    cases.rate(tid, int(n))
    await q.answer()
    lang = lang_of(q.message.chat_id)
    await q.edit_message_text(f"{t(lang, 'ask_rating')} {'⭐' * int(n)}")
    await context.bot.send_message(q.message.chat_id, t(lang, "thanks_rating"))


# ---------- commands ----------

async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    lang = lang_of(chat_id)
    if not context.args:
        await update.message.reply_text(t(lang, "status_usage"))
        return
    case = db.get_case(context.args[0])
    is_officer = case and officer_chat(case["officer_post"]) == chat_id
    if not case or (case["citizen_chat_id"] != chat_id and not is_officer):
        await update.message.reply_text(t(lang, "status_none"))
        return
    lines = [
        f"📋 {case['tracking_id']}",
        f"{STATUS_LABEL[case['status']][lang]}",
        f"👤 {case['officer_post']}",
        "",
    ]
    for e in db.get_events(case["tracking_id"]):
        label = STATUS_LABEL.get(e["to_status"], {}).get(lang, e["to_status"])
        lines.append(f"• {fmt_time(e['at'])} — {label} ({e['officer_post']})")
    await update.message.reply_text("\n".join(lines))


async def cmd_stopdata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lang = lang_of(update.effective_chat.id)
    await update.message.reply_text(t(lang, "stopdata_confirm"),
                                    reply_markup=kb([[(t(lang, "stopdata_yes"), "sd:yes")]]))


async def on_stopdata(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    lang = lang_of(q.message.chat_id)
    db.withdraw_citizen(q.message.chat_id)
    context.user_data.clear()
    await q.edit_message_text(t(lang, "stopdata_done"))


async def cmd_officer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    held = db.get_posts_for_chat(update.effective_chat.id)
    text = ("Tap the post this Telegram account holds. You can tap more than one.\n"
            "For a one-officer demo, tap “All posts”.")
    if held:
        text += "\n\nYou hold: " + "; ".join(held)
    rows = [[("📌 All posts (demo)", "op:all")]] + [[(p, f"op:{i}")] for i, p in enumerate(ALL_POSTS)]
    await update.message.reply_text(text, reply_markup=kb(rows))


async def on_officer_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    value = q.data.split(":")[1]
    posts = ALL_POSTS if value == "all" else [ALL_POSTS[int(value)]]
    for post in posts:
        db.register_officer(post, q.message.chat_id)
    await q.answer("Registered")
    label = "all posts" if value == "all" else posts[0]
    await context.bot.send_message(q.message.chat_id, f"✅ This account now receives new cases for: {label}\n"
                                                      "Cases arrive here with Accept / Escalate buttons.")


async def cmd_mycases(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    posts = [p for p in ALL_POSTS if officer_chat(p) == chat_id]
    if not posts:
        await update.message.reply_text("You don't hold any post. Use /officer to register.")
        return
    score = {r["post"]: r for r in cases.scorecard()}
    lines = []
    for p in posts:
        r = score.get(p)
        if not r:
            continue
        s = r["score"] if r["score"] is not None else "not enough data"
        lines.append(f"👤 {p}\n   Score: {s} · Open: {r['open']} · Reopens: {r['reopens']}")
    open_cases = db.cases_for_posts(posts)
    if open_cases:
        lines.append("\nOpen cases:")
        lines += [f"• {c['tracking_id']} — {c['category'] or '?'}, {c['village'] or '?'} — {c['status']}"
                  for c in open_cases]
    await update.message.reply_text("\n".join(lines) or "No cases yet.")


async def cmd_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    d = cases.dashboard_stats()
    lines = [
        "📊 GrievEye dashboard",
        f"Filed: {d['totals']['filed']} · Open: {d['totals']['open']} · "
        f"Confirmed fixed: {d['totals']['verified']}",
        "",
    ]
    for r in d["scorecard"]:
        s = r["score"] if r["score"] is not None else "n/a"
        lines.append(f"{s:>4} · {r['post']} (open {r['open']}, reopens {r['reopens']})")
    lines.append(f"\nFull view: http://localhost:{DASHBOARD_PORT}")
    await update.message.reply_text("\n".join(lines))


async def cmd_tick(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Demo only: move the clock ahead 48 hours and apply deadline rules."""
    db.advance_clock(48)
    results = cases.sweep()
    await update.message.reply_text(f"⏩ Clock moved ahead 48 hours. {len(results)} case(s) changed.")
    await announce_sweep(results)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if OFFICER_APP and context.bot is OFFICER_APP.bot:
        await update.message.reply_text(OFFICER_HELP)
        return
    await update.message.reply_text(
        "Send your complaint as text, a voice note, or a photo.\n"
        "/mydashboard – web page with all your complaints\n"
        "/status <ID> – check a case\n/language – change language\n/stopdata – delete my data"
        + ("" if OFFICER_APP else "\n\n" + OFFICER_HELP)
    )


OFFICER_HELP = (
    "Officers: new cases arrive here with Accept / Escalate buttons.\n"
    "/officer – claim your post\n/mycases – your open cases and score\n"
    "/mydashboard – your web desk (seniors also see their team)\n"
    "/status <ID> – one case\n"
    "Demo: /dashboard · /tick48"
)


async def cmd_mydashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send private links to this person's web views."""
    chat_id = update.effective_chat.id
    officer_bot_chat = bool(OFFICER_APP) and context.bot is OFFICER_APP.bot
    lines = []
    citizen = db.get_citizen(chat_id)
    if not officer_bot_chat and citizen and citizen.get("consent_at"):
        lines.append(f"📋 My complaints:\n{dashboard.citizen_link(chat_id)}")
    if officer_bot_chat or not OFFICER_APP:
        held = cases.posts_held_by(chat_id)
        busy = {p: len(db.cases_for_posts([p])) for p in held}
        # One link per role, opened on the busiest post; the page has a post switcher.
        is_top = lambda p: get_senior_post(p) is None  # noqa: E731
        for label, group in (("Officer desk", [p for p in held if not is_top(p) and cases.team_of(p)]),
                             ("Senior officer desk", [p for p in held if is_top(p)]),
                             ("Field staff desk", [p for p in held if not cases.team_of(p)])):
            if group:
                post = max(group, key=lambda p: busy[p])
                more = f" (+{len(group) - 1} more posts in the menu)" if len(group) > 1 else ""
                lines.append(f"🗂 {label} – {post}{more}:\n{dashboard.officer_link(chat_id, post)}")
    if not lines:
        lines.append("Nothing to show yet. Citizens: send a complaint first. Officers: use /officer.")
    lines.append("Open on a phone connected to the same Wi-Fi as the laptop.")
    await update.message.reply_text("\n\n".join(lines), disable_web_page_preview=True)


async def officer_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    held = cases.posts_held_by(update.effective_chat.id)
    text = "👮 GrievEye officer bot.\n\n" + OFFICER_HELP
    if held:
        text += f"\n\nThis account receives cases for {len(held)} post(s). See /mycases."
    else:
        text += "\n\nYou hold no post yet. Tap /officer to claim one."
    await update.message.reply_text(text)


async def officer_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pending_proof = db.get_setting(f"proof:{update.effective_chat.id}")
    if await skip_officer_location(update, context):
        return
    if pending_proof:
        await remind_proof(update, pending_proof)
    else:
        await update.message.reply_text("This bot is for officers. Cases arrive here automatically. /help")


async def officer_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await handle_officer_photo(update, context):
        await update.message.reply_text("You have no accepted case to resolve. Tap Accept on a case first.")


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    log.error("Error while handling an update", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        try:
            await context.bot.send_message(update.effective_chat.id, t(lang_of(update.effective_chat.id), "error"))
        except Exception:
            pass


# ---------- dashboard hooks and background rules ----------

def dashboard_route(tracking_id, post):
    """Called from the dashboard thread when triage staff route a case."""
    case = cases.route_triage(tracking_id, post)

    async def announce():
        await alert_officer(case)
        await tell_citizen(case, "routed")
    asyncio.run_coroutine_threadsafe(announce(), LOOP)


def dashboard_tick(hours):
    db.advance_clock(hours)
    asyncio.run_coroutine_threadsafe(announce_sweep(cases.sweep()), LOOP)


async def rules_loop():
    while True:
        await asyncio.sleep(60)
        try:
            await announce_sweep(cases.sweep())
        except Exception:
            log.exception("Deadline sweep failed")


CITIZEN_COMMANDS = [
    ("start", "Start / ಪ್ರಾರಂಭಿಸಿ"),
    ("mydashboard", "My complaints page / ನನ್ನ ದೂರುಗಳು"),
    ("status", "Check a complaint / ದೂರಿನ ಸ್ಥಿತಿ"),
    ("language", "Change language / ಭಾಷೆ"),
    ("stopdata", "Delete my data / ನನ್ನ ಮಾಹಿತಿ ಅಳಿಸಿ"),
    ("help", "Help"),
]
OFFICER_COMMANDS = [
    ("mycases", "Your open cases and score"),
    ("mydashboard", "Your web desk"),
    ("officer", "Claim your post"),
    ("status", "Look up one case"),
    ("dashboard", "Summary of all cases"),
    ("tick48", "Demo: move the clock 48 hours"),
    ("myid", "Show my chat ID"),
    ("help", "Help"),
]


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await update.message.reply_text(
        f"Your chat ID is: {chat_id}\n\nTo receive officer cases, put it in .env as "
        f"OFFICER_CHAT_ID={chat_id} and restart the bot, or just send /officer and tap your post."
    )


_seen_chats = set()


async def log_new_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Print each new person's chat ID in the terminal, so it is easy to find."""
    chat, user = update.effective_chat, update.effective_user
    if chat and (context.bot.id, chat.id) not in _seen_chats:
        _seen_chats.add((context.bot.id, chat.id))
        log.info(">>> Message from %s: chat_id = %s (via @%s)",
                 user.full_name if user else "?", chat.id, context.bot.username)


def add_common_handlers(app):
    app.add_handler(TypeHandler(Update, log_new_chat), group=-1)
    app.add_handler(CommandHandler("myid", cmd_myid))


def add_officer_handlers(app):
    app.add_handler(CommandHandler("officer", cmd_officer))
    app.add_handler(CommandHandler("mycases", cmd_mycases))
    app.add_handler(CommandHandler("dashboard", cmd_dashboard))
    app.add_handler(CommandHandler("tick48", cmd_tick))
    app.add_handler(CallbackQueryHandler(on_officer_button, pattern=r"^o:"))
    app.add_handler(CallbackQueryHandler(on_officer_register, pattern=r"^op:"))
    app.add_handler(CallbackQueryHandler(on_triage_route, pattern=r"^tr:"))
    app.add_handler(CallbackQueryHandler(on_proof_pick, pattern=r"^pf:"))


def build_apps():
    global APP, OFFICER_APP
    APP = (ApplicationBuilder().token(os.environ["TELEGRAM_BOT_TOKEN"])
           .read_timeout(30).write_timeout(60).build())
    add_common_handlers(APP)
    for name, fn in [("start", cmd_start), ("help", cmd_help), ("language", cmd_language),
                     ("status", cmd_status), ("stopdata", cmd_stopdata),
                     ("mydashboard", cmd_mydashboard)]:
        APP.add_handler(CommandHandler(name, fn))
    APP.add_handler(CallbackQueryHandler(on_language, pattern=r"^lang:"))
    APP.add_handler(CallbackQueryHandler(on_consent, pattern=r"^consent:"))
    APP.add_handler(CallbackQueryHandler(on_draft_button, pattern=r"^(vil|cat|cf):"))
    APP.add_handler(CallbackQueryHandler(on_verdict, pattern=r"^cv:"))
    APP.add_handler(CallbackQueryHandler(on_rating, pattern=r"^rt:"))
    APP.add_handler(CallbackQueryHandler(on_close_rating, pattern=r"^cr:"))
    APP.add_handler(CallbackQueryHandler(on_stopdata, pattern=r"^sd:"))
    APP.add_error_handler(on_error)

    if os.environ.get("OFFICER_BOT_TOKEN"):
        # Separate officer bot: officers get their own clean chat.
        OFFICER_APP = (ApplicationBuilder().token(os.environ["OFFICER_BOT_TOKEN"])
                       .read_timeout(30).write_timeout(60).build())
        add_common_handlers(OFFICER_APP)
        add_officer_handlers(OFFICER_APP)
        for name, fn in [("start", officer_start), ("help", cmd_help), ("status", cmd_status),
                         ("mydashboard", cmd_mydashboard)]:
            OFFICER_APP.add_handler(CommandHandler(name, fn))
        OFFICER_APP.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, officer_photo))
        OFFICER_APP.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, officer_text))
        OFFICER_APP.add_handler(MessageHandler(filters.LOCATION, officer_location_handler))
        OFFICER_APP.add_error_handler(on_error)
    else:
        # One bot plays both roles (officer buttons arrive in OFFICER_CHAT_ID).
        add_officer_handlers(APP)

    APP.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    APP.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    APP.add_handler(MessageHandler(filters.LOCATION, on_location))
    APP.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, on_photo))


async def run():
    global LOOP
    LOOP = asyncio.get_running_loop()
    apps = [a for a in (APP, OFFICER_APP) if a]
    for app in apps:
        await app.initialize()
    await APP.bot.set_my_commands(CITIZEN_COMMANDS + ([] if OFFICER_APP else OFFICER_COMMANDS[:-1]))
    if OFFICER_APP:
        await OFFICER_APP.bot.set_my_commands(OFFICER_COMMANDS)

    for app in apps:
        await app.start()
        await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    rules = asyncio.create_task(rules_loop())

    citizen_name = (await APP.bot.get_me()).username
    log.info("Citizen bot: @%s", citizen_name)
    if OFFICER_APP:
        log.info("Officer bot: @%s  (each officer must press Start in it once)",
                 (await OFFICER_APP.bot.get_me()).username)
    else:
        log.info("No OFFICER_BOT_TOKEN: officer alerts go through @%s to OFFICER_CHAT_ID", citizen_name)
    log.info("DC dashboard: http://localhost:%s   ·   all views: http://localhost:%s/demo",
             DASHBOARD_PORT, DASHBOARD_PORT)
    log.info("Phones on the same Wi-Fi use %s", dashboard.base_url())

    try:
        await asyncio.Event().wait()  # run until Ctrl+C
    finally:
        rules.cancel()
        for app in apps:
            if app.updater.running:
                await app.updater.stop()
            if app.running:
                await app.stop()
            await app.shutdown()


def main():
    db.init_db()
    build_apps()
    dashboard.HOOKS["route"] = dashboard_route
    dashboard.HOOKS["tick"] = dashboard_tick
    try:
        dashboard.start(DASHBOARD_PORT)
    except OSError:
        log.error("Port %s is already in use: GrievEye is probably running in another terminal. "
                  "Stop that one first (Ctrl+C there), then start again. Only one copy may run, "
                  "because Telegram gives each bot's messages to one program only.", DASHBOARD_PORT)
        sys.exit(1)
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        log.info("Stopped.")


if __name__ == "__main__":
    main()
