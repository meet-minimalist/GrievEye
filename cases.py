"""
Case state machine, routing rules and the officer scorecard.

Nothing here talks to Telegram. The bot (or the dashboard) calls these
functions, then sends whatever messages the result calls for. That keeps the
rules identical when the Telegram adapter is swapped for WhatsApp.
"""
import os
import statistics

import database as db
import geo
from officer_directory import (
    ALL_POSTS, CATEGORIES, SENIOR_POSTS, TARGET_DAYS, get_officer_post, get_senior_post, get_team,
)

OFFICER_FALLBACK = int(os.environ["OFFICER_CHAT_ID"]) if os.environ.get("OFFICER_CHAT_ID") else None

ACK_HOURS = 48          # officer must accept within this, or the case escalates
VERIFY_DAYS = 7         # citizen silence after "resolved" -> RESOLVED_UNVERIFIED
MAX_REOPENS = 2         # the second "No" sends the case to the senior post
MIN_CLOSED_FOR_SCORE = 10
TRIAGE_CONFIDENCE = 0.6

CLOSED = ("VERIFIED", "RESOLVED_UNVERIFIED")
FINISHED = CLOSED + ("REJECTED",)   # no longer open; REJECTED = marked as spam

# Spam: strikes within the window; at the threshold the citizen cannot file for BAN_DAYS (0 = permanent).
SPAM_WINDOW_DAYS = 90
SPAM_BAN_THRESHOLD = int(os.environ.get("SPAM_BAN_THRESHOLD", 3))
SPAM_BAN_DAYS = float(os.environ.get("SPAM_BAN_DAYS", 30))
SPAM_REASONS = {
    "fake": "Fake / not a real problem",
    "abusive": "Abusive language",
    "duplicate": "Duplicate of another complaint",
    "irrelevant": "Not a complaint (joke, ad, forward)",
}

ALLOWED = {
    "TRIAGE": {"OPEN", "REJECTED"},
    "REJECTED": {"OPEN"},                                # restored on appeal
    "OPEN": {"ACCEPTED", "ESCALATED", "OPEN", "REJECTED"},       # OPEN -> OPEN = assigned down
    "ACCEPTED": {"ESCALATED", "RESOLVED_PENDING", "OPEN", "REJECTED"},
    "ESCALATED": {"ACCEPTED", "ESCALATED", "OPEN", "REJECTED"},
    "RESOLVED_PENDING": {"VERIFIED", "REOPENED", "RESOLVED_UNVERIFIED"},
    "REOPENED": {"ACCEPTED", "ESCALATED", "OPEN", "REJECTED"},
    "VERIFIED": set(),
    "RESOLVED_UNVERIFIED": set(),
}

# Escalation reasons. Only the "penalised" ones count against the officer.
ESCALATION_REASONS = {
    "outside_powers": ("Outside my powers", False),
    "needs_approval": ("Needs senior approval", False),
    "overdue": ("Not accepted within 48 hours", True),
    "reopened_twice": ("Citizen said not fixed twice", True),
}


class InvalidTransition(Exception):
    pass


def officer_chat(post):
    """The Telegram chat that holds a post: whoever claimed it, else the fallback chat."""
    return db.get_officer_chat(post) or OFFICER_FALLBACK


def posts_held_by(chat_id):
    return [p for p in ALL_POSTS if officer_chat(p) == chat_id]


def team_of(post):
    """Posts that escalate to this post."""
    return [p for p, senior in SENIOR_POSTS.items() if senior == post]


def _move(case, to_status, actor, note=None, proof_file_id=None, new_post=None, at=None):
    """The only place a case changes status. Rejects anything not in ALLOWED."""
    from_status = case["status"]
    if to_status not in ALLOWED.get(from_status, set()):
        raise InvalidTransition(f"{case['tracking_id']}: {from_status} -> {to_status}")
    at = at or db.now()
    post = new_post or case["officer_post"]
    db.update_case(case["tracking_id"], status=to_status, officer_post=post, updated_at=at)
    db.add_event(case["tracking_id"], at, actor, post, from_status, to_status, note,
                 proof_file_id, from_post=case["officer_post"])
    return db.get_case(case["tracking_id"])


# ---------- actions ----------

def create_case(citizen_chat_id, citizen_name, village, category, description, raw_text,
                media_type=None, media_file_id=None, confidence=1.0, restricted=False,
                lat=None, lon=None, location_source=None):
    """Create a case. Low AI confidence sends it to the triage queue first."""
    post = get_officer_post(village, category)
    status = "TRIAGE" if confidence < TRIAGE_CONFIDENCE else "OPEN"
    at = db.now()
    tid = db.insert_case(
        citizen_chat_id=citizen_chat_id, citizen_name=citizen_name, village=village,
        category=category, description=description, raw_text=raw_text,
        media_type=media_type, media_file_id=media_file_id, ai_confidence=confidence,
        restricted=int(bool(restricted)), original_post=post, officer_post=post,
        status=status, created_at=at, updated_at=at,
        lat=lat, lon=lon, location_source=location_source,
    )
    db.add_event(tid, at, "citizen", post, None, status, "Filed")
    return db.get_case(tid)


def route_triage(tracking_id, post):
    case = db.get_case(tracking_id)
    db.update_case(tracking_id, original_post=post)
    return _move(case, "OPEN", "triage", note="Routed by triage", new_post=post)


def accept(tracking_id):
    return _move(db.get_case(tracking_id), "ACCEPTED", "officer", note="Accepted")


def escalate(tracking_id, reason, actor="officer"):
    """Send the case to the senior post. Returns the case, or None at the top of the chain."""
    case = db.get_case(tracking_id)
    senior = get_senior_post(case["officer_post"])
    if not senior:
        return None
    return _move(case, "ESCALATED", actor, note=reason, new_post=senior)


def assign_down(tracking_id, to_post):
    """An officer hands a case to a post below them. The new post must Accept it,
    and its 48-hour clock starts. Not a penalty for either officer."""
    case = db.get_case(tracking_id)
    if to_post not in get_team(case["officer_post"]):
        raise InvalidTransition(f"{to_post} is not below {case['officer_post']}")
    return _move(case, "OPEN", "officer", note=f"Assigned by {case['officer_post']}", new_post=to_post)


def set_proof_location(tracking_id, lat, lon):
    """Where the officer was when resolving. Distance to the complaint is kept for the dashboards."""
    case = db.get_case(tracking_id)
    distance = None
    if case["lat"] is not None:
        distance = geo.distance_m(case["lat"], case["lon"], lat, lon)
    db.update_case(tracking_id, proof_lat=lat, proof_lon=lon, proof_distance_m=distance)
    return distance


def is_assignment(event):
    return event["to_status"] == "OPEN" and (event["note"] or "").startswith("Assigned by")


NO_PROOF_NOTE = "Marked resolved WITHOUT photo proof"


def resolve(tracking_id, proof_file_id, allow_no_proof=False):
    """Officer marks the case fixed. A photo is expected; without one the event is flagged."""
    if not proof_file_id and not allow_no_proof:
        raise InvalidTransition("Proof photo is required to mark a case resolved")
    note = "Marked resolved with proof" if proof_file_id else NO_PROOF_NOTE
    return _move(db.get_case(tracking_id), "RESOLVED_PENDING", "officer",
                 note=note, proof_file_id=proof_file_id)


def citizen_verdict(tracking_id, answer):
    """answer: yes / partly / no. Returns (case, outcome) where outcome is
    verified, reopened or escalated."""
    case = db.get_case(tracking_id)
    if answer == "yes":
        return _move(case, "VERIFIED", "citizen", note="Citizen confirmed fixed"), "verified"

    note = "Citizen: partly fixed" if answer == "partly" else "Citizen: not fixed"
    db.update_case(tracking_id, reopen_count=case["reopen_count"] + 1)
    case = _move(db.get_case(tracking_id), "REOPENED", "citizen", note=note)
    if case["reopen_count"] >= MAX_REOPENS:
        escalated = escalate(tracking_id, "reopened_twice", actor="system")
        if escalated:
            return escalated, "escalated"
    return case, "reopened"


def spam_strikes(chat_id):
    """Spam marks against a citizen in the window, not counting ones overturned on appeal."""
    since = db.now() - SPAM_WINDOW_DAYS * 86400
    return sum(1 for c in db.all_cases()
               if c["citizen_chat_id"] == chat_id and c["status"] == "REJECTED"
               and c["appeal_status"] != "overturned" and c["updated_at"] >= since)


def banned_until(chat_id):
    """When a citizen's ban ends (a timestamp), or None if they may file complaints."""
    until = (db.get_citizen(chat_id) or {}).get("banned_until")
    return until if until and until > db.now() else None


def mark_spam(tracking_id, reason):
    """An officer rejects a complaint as spam. Returns (case, strikes, banned_until)."""
    case = db.get_case(tracking_id)
    by = case["officer_post"]
    db.update_case(tracking_id, spam_reason=reason, spam_by=by, appeal_status=None)
    case = _move(case, "REJECTED", "officer", note=f"Marked as spam: {SPAM_REASONS.get(reason, reason)}")
    if case["is_seed"]:
        return case, 0, None
    strikes = spam_strikes(case["citizen_chat_id"])
    until = None
    if strikes >= SPAM_BAN_THRESHOLD:
        until = db.now() + (SPAM_BAN_DAYS * 86400 if SPAM_BAN_DAYS > 0 else 100 * 365 * 86400)
        db.upsert_citizen(case["citizen_chat_id"], banned_until=until)
    return case, strikes, until


def appeal_reviewer(case):
    """The senior of the post that marked the spam (None: only the DC dashboard can decide)."""
    return get_senior_post(case["spam_by"]) if case["spam_by"] else None


def start_appeal(tracking_id):
    db.update_case(tracking_id, appeal_status="pending")
    return db.get_case(tracking_id)


def decide_appeal(tracking_id, restore):
    """Restore: the case reopens with the post that marked it, the strike is removed, and a ban
    that no longer reaches the threshold is lifted. Otherwise the spam mark stands."""
    case = db.get_case(tracking_id)
    if case["status"] != "REJECTED" or case["appeal_status"] in ("upheld", "overturned"):
        raise InvalidTransition(f"{tracking_id}: no open appeal")
    if not restore:
        db.update_case(tracking_id, appeal_status="upheld")
        return db.get_case(tracking_id)
    db.update_case(tracking_id, appeal_status="overturned")
    case = _move(db.get_case(tracking_id), "OPEN", "triage", note="Spam mark overturned on appeal",
                 new_post=case["spam_by"])
    if spam_strikes(case["citizen_chat_id"]) < SPAM_BAN_THRESHOLD:
        db.upsert_citizen(case["citizen_chat_id"], banned_until=None)
    return case


def lift_ban(chat_id):
    db.upsert_citizen(chat_id, banned_until=None)


def rate(tracking_id, rating):
    db.update_case(tracking_id, citizen_rating=int(rating))


def sweep():
    """Apply the time rules. Returns a list of (kind, case) for the bot to announce."""
    results = []
    t = db.now()
    live = lambda rows: [c for c in rows if not c["is_seed"]]  # seed history never triggers alerts
    for case in live(db.cases_with_status("OPEN", "ESCALATED", "REOPENED")):
        if t - case["updated_at"] > ACK_HOURS * 3600:
            escalated = escalate(case["tracking_id"], "overdue", actor="system")
            if escalated:
                results.append(("escalated", escalated))
    for case in live(db.cases_with_status("RESOLVED_PENDING")):
        if t - case["updated_at"] > VERIFY_DAYS * 86400:
            closed = _move(case, "RESOLVED_UNVERIFIED", "system",
                           note="No reply from citizen in 7 days")
            results.append(("unverified", closed))
    return results


# ---------- scorecard ----------

def _post_metrics(post, cases_by_id, events):
    t = db.now()
    mine = [e for e in events if e["officer_post"] == post]

    # Responsiveness: each assignment should get an Accept from this post within 48 h.
    assignments = [e for e in mine if e["to_status"] in ("OPEN", "ESCALATED", "REOPENED")]
    acked = due = 0
    for a in assignments:
        accepted = next((e for e in mine if e["tracking_id"] == a["tracking_id"]
                         and e["to_status"] == "ACCEPTED" and e["at"] >= a["at"]), None)
        on_time = accepted and accepted["at"] - a["at"] <= ACK_HOURS * 3600
        if on_time:
            acked += 1
            due += 1
        elif accepted or t - a["at"] > ACK_HOURS * 3600:
            due += 1

    resolve_marks = [e for e in mine if e["to_status"] == "RESOLVED_PENDING"]
    reopens = [e for e in events if e["to_status"] == "REOPENED" and e["from_post"] == post]
    spam_marked = [c for c in cases_by_id.values() if c["spam_by"] == post]
    overturned = sum(1 for c in spam_marked if c["appeal_status"] == "overturned")

    # Closed cases are credited to the post that last marked them resolved.
    last_resolver = {}
    for e in events:
        if e["to_status"] == "RESOLVED_PENDING":
            last_resolver[e["tracking_id"]] = (e["officer_post"], e["at"])
    closed = [c for c in cases_by_id.values()
              if c["status"] in CLOSED and last_resolver.get(c["tracking_id"], (None,))[0] == post]
    verified = sum(1 for c in closed if c["status"] == "VERIFIED")
    unverified = len(closed) - verified

    days, speed_scores = [], []
    for c in closed:
        d = max((last_resolver[c["tracking_id"]][1] - c["created_at"]) / 86400, 0.05)
        days.append(d)
        speed_scores.append(min(1.0, TARGET_DAYS.get(c["category"], 7) / d))
    ratings = [c["citizen_rating"] for c in closed if c["citizen_rating"]]

    escalated_out = [e for e in events if e["to_status"] == "ESCALATED" and e["from_post"] == post]
    penalised = sum(1 for e in escalated_out if ESCALATION_REASONS.get(e["note"], ("", False))[1])

    confirmed_rate = (verified + 0.5 * unverified) / len(closed) if closed else 0
    # A spam mark overturned on appeal counts like a reopen: the officer dismissed a real problem.
    reopen_rate = (len(reopens) + overturned) / len(resolve_marks) if resolve_marks else (1 if overturned else 0)
    avg_rating = statistics.mean(ratings) if ratings else None
    ack_rate = acked / due if due else 1.0
    speed = statistics.mean(speed_scores) if speed_scores else 0

    score = None
    if len(closed) >= MIN_CLOSED_FOR_SCORE:
        score = round(100 * (
            0.35 * confirmed_rate
            + 0.25 * speed
            + 0.20 * (1 - min(reopen_rate, 1))
            + 0.10 * ((avg_rating or 3) / 5)
            + 0.10 * ack_rate
        ))

    open_now = sum(1 for c in cases_by_id.values()
                   if c["officer_post"] == post and c["status"] not in FINISHED + ("TRIAGE",))
    return {
        "post": post,
        "score": score,
        "open": open_now,
        "closed": len(closed),
        "verified": verified,
        "unverified": unverified,
        "confirmed_rate": round(confirmed_rate * 100),
        "median_days": round(statistics.median(days), 1) if days else None,
        "reopens": len(reopens),
        "spam_marked": len(spam_marked),
        "spam_overturned": overturned,
        "reopen_rate": round(reopen_rate * 100),
        "avg_rating": round(avg_rating, 1) if avg_rating else None,
        "ack_rate": round(ack_rate * 100),
        "escalations_valid": len(escalated_out) - penalised,
        "escalations_penalised": penalised,
        # Each part of the score on a 0-100 scale, for the officer's breakdown.
        "parts": {
            "Citizen-confirmed (35%)": round(confirmed_rate * 100),
            "Speed vs target (25%)": round(speed * 100),
            "Few reopens (20%)": round((1 - min(reopen_rate, 1)) * 100),
            "Citizen rating (10%)": round(((avg_rating or 3) / 5) * 100),
            "Accepted in 48 h (10%)": round(ack_rate * 100),
        },
    }


def scorecard():
    cases_by_id = {c["tracking_id"]: c for c in db.all_cases()}
    events = db.all_events()
    rows = [_post_metrics(p, cases_by_id, events) for p in ALL_POSTS]
    rows = [r for r in rows if r["open"] or r["closed"] or r["reopens"]]
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0), -r["open"]))
    return rows


def dashboard_stats():
    cases = db.all_cases()
    closed = [c for c in cases if c["status"] in CLOSED]
    events = db.all_events()
    resolved_at = {}
    for e in events:
        if e["to_status"] == "RESOLVED_PENDING":
            resolved_at[e["tracking_id"]] = e["at"]
    days = [(resolved_at[c["tracking_id"]] - c["created_at"]) / 86400
            for c in closed if c["tracking_id"] in resolved_at]

    by_category = {cat: 0 for cat in CATEGORIES}
    for c in cases:
        if c["category"] in by_category:
            by_category[c["category"]] += 1

    feed = []
    for e in db.recent_events():
        restricted = db.get_case(e["tracking_id"])["restricted"]
        feed.append({
            "tracking_id": e["tracking_id"],
            "at": e["at"],
            "to_status": "ASSIGNED" if is_assignment(e) else e["to_status"],
            "actor": e["actor"],
            "post": e["officer_post"],
            "note": ESCALATION_REASONS.get(e["note"], (e["note"],))[0],
            "village": None if restricted else e["village"],
            "category": "Restricted" if restricted else e["category"],
        })

    triage = [{
        "tracking_id": c["tracking_id"],
        "village": c["village"],
        "category": c["category"],
        "description": "Restricted case" if c["restricted"] else c["description"],
        "confidence": c["ai_confidence"],
        "suggested_post": c["officer_post"],
    } for c in cases if c["status"] == "TRIAGE"]

    return {
        "now": db.now(),
        "clock_offset_hours": round(float(db.get_setting("clock_offset", 0)) / 3600),
        "totals": {
            "filed": len(cases),
            "open": sum(1 for c in cases if c["status"] not in FINISHED),
            "verified": sum(1 for c in cases if c["status"] == "VERIFIED"),
            "avg_days": round(statistics.mean(days), 1) if days else None,
        },
        "scorecard": scorecard(),
        "by_category": by_category,
        "feed": feed,
        "triage": triage,
        "posts": ALL_POSTS,
        "spam": spam_overview(cases),
    }


# ---------- role views (citizen, officer, senior officer) ----------

OPEN_STATES = ("OPEN", "ACCEPTED", "ESCALATED", "REOPENED", "RESOLVED_PENDING")


def spam_overview(cases):
    """Citizens with spam strikes, and appeals waiting for a decision (for the DC dashboard)."""
    names = {c["chat_id"]: c for c in db.all_citizens()}
    flagged = []
    for chat_id in {c["citizen_chat_id"] for c in cases if c["status"] == "REJECTED" and not c["is_seed"]}:
        strikes = spam_strikes(chat_id)
        until = banned_until(chat_id)
        if strikes or until:
            name = (names.get(chat_id, {}).get("name") or "Citizen").split()[0]
            flagged.append({"chat_id": chat_id, "name": name, "strikes": strikes, "banned_until": until})
    appeals = [{"tracking_id": c["tracking_id"], "description": c["description"],
                "reason": SPAM_REASONS.get(c["spam_reason"], c["spam_reason"]), "marked_by": c["spam_by"]}
               for c in cases if c["status"] == "REJECTED" and c["appeal_status"] == "pending"]
    return {"flagged": sorted(flagged, key=lambda f: -f["strikes"]), "appeals": appeals,
            "threshold": SPAM_BAN_THRESHOLD}


def _reason(note):
    return ESCALATION_REASONS.get(note, (note,))[0]


def citizen_view(chat_id):
    """Everything a citizen may see about their own complaints."""
    citizen = db.get_citizen(chat_id) or {}
    out = []
    for c in sorted((c for c in db.all_cases() if c["citizen_chat_id"] == chat_id),
                    key=lambda c: -c["created_at"]):
        events = db.get_events(c["tracking_id"])
        out.append({
            "tracking_id": c["tracking_id"],
            "status": c["status"],
            "village": c["village"],
            "category": c["category"],
            "description": c["description"],
            "officer_post": c["officer_post"],
            "created_at": c["created_at"],
            "reopen_count": c["reopen_count"],
            "rating": c["citizen_rating"],
            "has_proof": bool(db.last_proof(c["tracking_id"])),
            "spam_reason": SPAM_REASONS.get(c["spam_reason"]) if c["status"] == "REJECTED" else None,
            "appeal_status": c["appeal_status"],
            "media_type": c["media_type"],
            "timeline": [{"at": e["at"], "to_status": e["to_status"], "post": e["officer_post"],
                          "note": _reason(e["note"]) if e["to_status"] == "ESCALATED"
                          else e["note"] if is_assignment(e) else None}
                         for e in events],
        })
    return {"name": citizen.get("name"), "language": citizen.get("language") or "en",
            "now": db.now(), "cases": out}


def officer_view(post):
    """One post's work: queue, cases escalated in, own score, and (for seniors) the team."""
    t = db.now()
    all_cases = db.all_cases()
    events = db.all_events()
    score = {r["post"]: r for r in scorecard_all()}

    def row(c):
        last = next((e for e in reversed(events) if e["tracking_id"] == c["tracking_id"]), None)
        waiting_h = (t - c["updated_at"]) / 3600
        return {
            "tracking_id": c["tracking_id"],
            "status": c["status"],
            "officer_post": c["officer_post"],
            "village": c["village"],
            "category": "Restricted" if c["restricted"] and c["officer_post"] != post else c["category"],
            "description": c["description"],
            "citizen": (c["citizen_name"] or "Citizen").split()[0],
            "age_days": round((t - c["created_at"]) / 86400, 1),
            "waiting_hours": round(waiting_h),
            "overdue": c["status"] in ("OPEN", "ESCALATED", "REOPENED") and waiting_h > ACK_HOURS,
            "reopen_count": c["reopen_count"],
            "escalated_from": last["from_post"] if last and last["to_status"] == "ESCALATED" else None,
            "escalation_reason": _reason(last["note"]) if last and last["to_status"] == "ESCALATED" else None,
            "assigned_by": last["from_post"] if last and is_assignment(last) else None,
            "map": geo.maps_link(c["lat"], c["lon"]) if c["lat"] is not None else None,
            "restricted": bool(c["restricted"]),
        }

    mine = [c for c in all_cases if c["officer_post"] == post and c["status"] in OPEN_STATES]
    mine.sort(key=lambda c: c["updated_at"])
    queue = [row(c) for c in mine]
    escalated_in = [r for r in queue if r["escalated_from"] and r["escalated_from"] != post]

    closed_ids = {e["tracking_id"] for e in events
                  if e["to_status"] == "RESOLVED_PENDING" and e["officer_post"] == post}
    recent_closed = sorted((c for c in all_cases if c["tracking_id"] in closed_ids and c["status"] in CLOSED),
                           key=lambda c: -c["updated_at"])[:8]

    team = team_of(post)
    team_rows = [score.get(p) or {"post": p, "score": None, "open": 0, "closed": 0, "reopens": 0,
                                  "ack_rate": 100, "median_days": None, "avg_rating": None,
                                  "escalations_valid": 0, "escalations_penalised": 0}
                 for p in team]
    for r in team_rows:
        r["overdue"] = sum(1 for c in all_cases if c["officer_post"] == r["post"]
                           and c["status"] in ("OPEN", "ESCALATED", "REOPENED")
                           and t - c["updated_at"] > ACK_HOURS * 3600)
    escalation_log = [{
        "tracking_id": e["tracking_id"], "at": e["at"], "from_post": e["from_post"],
        "to_post": e["officer_post"], "reason": _reason(e["note"]),
        "penalised": ESCALATION_REASONS.get(e["note"], ("", False))[1],
    } for e in reversed(events) if e["to_status"] == "ESCALATED" and e["from_post"] in team][:15]

    below = get_team(post)
    assigned_down = [row(c) for c in all_cases
                     if c["officer_post"] in below and c["status"] in OPEN_STATES
                     and any(is_assignment(e) and e["from_post"] == post and e["tracking_id"] == c["tracking_id"]
                             for e in events)]
    return {
        "post": post,
        "senior_post": get_senior_post(post),
        "assigned_down": assigned_down,
        "is_senior": bool(team),
        "now": t,
        "me": score.get(post),
        "queue": queue,
        "escalated_in": escalated_in,
        "recent_closed": [{"tracking_id": c["tracking_id"], "status": c["status"],
                           "category": c["category"], "village": c["village"],
                           "rating": c["citizen_rating"], "reopen_count": c["reopen_count"],
                           "proof_distance": geo.describe_distance(c["proof_distance_m"]),
                           "has_location": c["lat"] is not None,
                           "proof_shared": c["proof_lat"] is not None}
                          for c in recent_closed],
        "team": team_rows,
        "escalation_log": escalation_log,
    }


def scorecard_all():
    """Scorecard rows for every post, including posts with no cases yet."""
    cases_by_id = {c["tracking_id"]: c for c in db.all_cases()}
    events = db.all_events()
    return [_post_metrics(p, cases_by_id, events) for p in ALL_POSTS]
