"""
Load 5 weeks of realistic past cases so the scorecard is not empty on stage.

    python seed_demo.py          # wipe all cases, then seed
    python seed_demo.py --keep   # add seed cases without wiping

Four posts get different "personalities". AEE, PWD Kanakapura is the clearly
weak one (slow, many reopens), which gives the dashboard a story to tell.
Citizens, officer registrations and consent records are never touched.
"""
import random
import sys

import database as db

random.seed(7)
DAY = 86400
HOUR = 3600

# post: (village, category list, count, ack hours, resolve days, reopen chance, verify chance, rating range)
PROFILES = {
    "PDO, Hosahalli GP": ("Hosahalli", ["Water Supply", "Sanitation", "Roads"], 13,
                          (2, 20), (1, 4), 0.10, 0.85, (4, 5)),
    "AE, BESCOM Hosahalli": ("Hosahalli", ["Electricity"], 12, (1, 12), (0.5, 2.5), 0.05, 0.9, (4, 5)),
    "AEE, PWD Kanakapura": ("Kanakapura", ["Roads"], 15, (30, 90), (5, 12), 0.5, 0.5, (1, 3)),
    "Village Accountant, Kanakapura": ("Kanakapura", ["Land Records"], 13, (6, 40), (5, 12),
                                       0.2, 0.7, (2, 4)),
}

ISSUES = {
    "Water Supply": ["No drinking water supply for 3 days", "Borewell pump is not working",
                     "Water pipe leaking near the temple"],
    "Sanitation": ["Drain is blocked and overflowing", "Garbage not collected for a week"],
    "Roads": ["Large potholes on the main road", "Road to the school is damaged",
              "Culvert collapsed after rain"],
    "Electricity": ["Streetlight not working for a week", "Frequent power cuts at night",
                    "Transformer sparking near the market"],
    "Land Records": ["RTC shows the wrong owner name", "Khata transfer pending for 2 months",
                     "Survey sketch not issued"],
}

NAMES = ["Lakshmamma", "Ramesh", "Shivanna", "Geetha", "Manjunath", "Savitha", "Nagaraj",
         "Kavya", "Basavaraj", "Renuka", "Mahesh", "Shobha"]


def timeline(post, created, i, n, ack, days, p_reopen, p_verify):
    """Return the list of (at, actor, from, to, note) events for one case."""
    events = [(created, "citizen", None, "OPEN", "Filed")]
    t = created + random.uniform(*ack) * HOUR
    if i == n - 1:
        return events  # never accepted: shows as overdue work
    events.append((t, "officer", "OPEN", "ACCEPTED", "Accepted"))
    if i == n - 2:
        return events  # accepted, still being worked on
    reopened = False
    while True:
        t += random.uniform(*days) * DAY
        events.append((t, "officer", "ACCEPTED", "RESOLVED_PENDING", "Marked resolved with proof"))
        if not reopened and random.random() < p_reopen:
            reopened = True
            t += random.uniform(0.2, 1) * DAY
            events.append((t, "citizen", "RESOLVED_PENDING", "REOPENED", "Citizen: not fixed"))
            t += random.uniform(*ack) * HOUR / 2
            events.append((t, "officer", "REOPENED", "ACCEPTED", "Accepted"))
            continue
        break
    t += random.uniform(0.1, 1) * DAY
    if random.random() < p_verify:
        events.append((t, "citizen", "RESOLVED_PENDING", "VERIFIED", "Citizen confirmed fixed"))
    else:
        events.append((t, "system", "RESOLVED_PENDING", "RESOLVED_UNVERIFIED",
                       "No reply from citizen in 7 days"))
    return events


def seed():
    now = db.now()
    count = 0
    for post, (village, categories, n, ack, days, p_reopen, p_verify, rating) in PROFILES.items():
        for i in range(n):
            category = random.choice(categories)
            # Build the story from time 0, then place it so it ends before now.
            story = timeline(post, 0, i, n, ack, days, p_reopen, p_verify)
            if i >= n - 2:   # the open cases are recent
                end = now - random.uniform(0.3, 1.5) * DAY
            else:            # closed cases ended some time in the last 4 weeks
                end = now - random.uniform(0.5, 28) * DAY
            shift = end - story[-1][0]
            events = [(at + shift, *rest) for at, *rest in story]
            created = events[0][0]
            status = events[-1][3]
            reopens = sum(1 for e in events if e[3] == "REOPENED")
            tid = db.insert_case(
                citizen_chat_id=0, citizen_name=random.choice(NAMES), village=village,
                category=category, description=random.choice(ISSUES[category]),
                raw_text=None, ai_confidence=round(random.uniform(0.7, 0.98), 2),
                original_post=post, officer_post=post, status=status, reopen_count=reopens,
                citizen_rating=random.randint(*rating) if status == "VERIFIED" else None,
                is_seed=1, created_at=created, updated_at=events[-1][0],
            )
            for at, actor, frm, to, note in events:
                db.add_event(tid, at, actor, post, frm, to, note)
            count += 1

    # One low-confidence case waiting in the triage queue.
    tid = db.insert_case(
        citizen_chat_id=0, citizen_name="Hanumanthappa", village="Kanakapura", category=None,
        description="Something about the ration shop being closed on distribution days",
        ai_confidence=0.41, original_post="Taluk Office, Duty Officer",
        officer_post="Taluk Office, Duty Officer", status="TRIAGE", is_seed=1,
        created_at=now - 5 * HOUR, updated_at=now - 5 * HOUR,
    )
    db.add_event(tid, now - 5 * HOUR, "citizen", "Taluk Office, Duty Officer", None, "TRIAGE", "Filed")
    return count + 1


if __name__ == "__main__":
    db.init_db()
    if "--keep" not in sys.argv:
        db.reset_all()
    print(f"Seeded {seed()} demo cases.")
