"""
Officer directory — maps (village, category) to the responsible officer POST.

Cases are routed to a post, never to a person, so transfers don't break routing.
A post is linked to a Telegram chat when an officer runs /officer in the bot
(stored in the `officers` table). Posts with no linked chat fall back to
OFFICER_CHAT_ID from .env, so the demo works with a single officer phone.

For the real deployment this becomes the full
village -> Gram Panchayat -> taluk -> department -> post -> phone mapping.
"""

TALUK_CODE = "KNK"

CATEGORIES = [
    "Water Supply",
    "Electricity",
    "Roads",
    "Sanitation",
    "Land Records",
    "Stray Animals",
    "Other",
]

CATEGORY_KN = {
    "Water Supply": "ಕುಡಿಯುವ ನೀರು",
    "Electricity": "ವಿದ್ಯುತ್",
    "Roads": "ರಸ್ತೆ",
    "Sanitation": "ನೈರ್ಮಲ್ಯ",
    "Land Records": "ಭೂ ದಾಖಲೆಗಳು",
    "Stray Animals": "ಬೀದಿ ಪ್ರಾಣಿಗಳು",
    "Other": "ಇತರೆ",
}

# Target days to resolve, per category. Used for the speed part of the score.
TARGET_DAYS = {
    "Water Supply": 3,
    "Electricity": 2,
    "Roads": 10,
    "Sanitation": 4,
    "Land Records": 15,
    "Stray Animals": 5,
    "Other": 7,
}

VILLAGES = ["Hosahalli", "Kanakapura"]

VILLAGE_KN = {
    "Hosahalli": "ಹೊಸಹಳ್ಳಿ",
    "Kanakapura": "ಕನಕಪುರ",
}

# village -> category -> officer post
OFFICER_POSTS = {
    "Hosahalli": {
        "Water Supply": "PDO, Hosahalli GP",
        "Electricity": "AE, BESCOM Hosahalli",
        "Roads": "PDO, Hosahalli GP",
        "Sanitation": "PDO, Hosahalli GP",
        "Land Records": "Village Accountant, Hosahalli",
        "Stray Animals": "PDO, Hosahalli GP",
        "Other": "Taluk Office, Duty Officer",
    },
    "Kanakapura": {
        "Water Supply": "PDO, Kanakapura GP",
        "Electricity": "AE, BESCOM Kanakapura",
        "Roads": "AEE, PWD Kanakapura",
        "Sanitation": "PDO, Kanakapura GP",
        "Land Records": "Village Accountant, Kanakapura",
        "Stray Animals": "PDO, Kanakapura GP",
        "Other": "Taluk Office, Duty Officer",
    },
}

# post -> the post a case goes to on escalation (None = top of the chain)
SENIOR_POSTS = {
    "PDO, Hosahalli GP": "EO, Kanakapura Taluk Panchayat",
    "PDO, Kanakapura GP": "EO, Kanakapura Taluk Panchayat",
    "AE, BESCOM Hosahalli": "AEE, BESCOM Kanakapura",
    "AE, BESCOM Kanakapura": "AEE, BESCOM Kanakapura",
    "AEE, PWD Kanakapura": "EE, PWD Ramanagara",
    "Village Accountant, Hosahalli": "Revenue Inspector, Kanakapura",
    "Village Accountant, Kanakapura": "Revenue Inspector, Kanakapura",
    "Taluk Office, Duty Officer": "Tahsildar, Kanakapura",
    # Field staff: officers assign work down to these posts.
    "Waterman, Hosahalli GP": "PDO, Hosahalli GP",
    "Sanitation Supervisor, Hosahalli GP": "PDO, Hosahalli GP",
    "Waterman, Kanakapura GP": "PDO, Kanakapura GP",
    "Sanitation Supervisor, Kanakapura GP": "PDO, Kanakapura GP",
    "Lineman, BESCOM Hosahalli": "AE, BESCOM Hosahalli",
    "Lineman, BESCOM Kanakapura": "AE, BESCOM Kanakapura",
    "JE, PWD Kanakapura": "AEE, PWD Kanakapura",
    "Revenue Inspector, Kanakapura": "Tahsildar, Kanakapura",
    "EO, Kanakapura Taluk Panchayat": None,
    "AEE, BESCOM Kanakapura": None,
    "EE, PWD Ramanagara": None,
    "Tahsildar, Kanakapura": None,
}

DEFAULT_POST = "Taluk Office, Duty Officer"

ALL_POSTS = list(SENIOR_POSTS.keys())


def get_officer_post(village: str, category: str) -> str:
    village_map = OFFICER_POSTS.get(village)
    if not village_map:
        return DEFAULT_POST
    return village_map.get(category, DEFAULT_POST)


def get_senior_post(post: str):
    return SENIOR_POSTS.get(post)


def get_team(post: str):
    """Every post below this one (direct reports first, then theirs)."""
    direct = [p for p, senior in SENIOR_POSTS.items() if senior == post]
    below = list(direct)
    for p in direct:
        below += get_team(p)
    return below
