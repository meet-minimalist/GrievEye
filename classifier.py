"""
Claude-based intake: turns a messy complaint (text, voice transcript, photo)
into structured fields. Uses a forced tool call so the output is always valid.
"""
import base64
import os

from anthropic import Anthropic

from officer_directory import CATEGORIES, VILLAGES, VILLAGE_KN

MODEL = os.environ.get("CLAUDE_MODEL", "claude-haiku-4-5-20251001")

_client = None


def get_client():
    global _client
    if _client is None:
        headers = {}
        # Keys that are not scoped to a workspace need this header.
        if os.environ.get("ANTHROPIC_WORKSPACE_ID"):
            headers["anthropic-workspace-id"] = os.environ["ANTHROPIC_WORKSPACE_ID"]
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], default_headers=headers)
    return _client


# Keywords: English, Kannada script, and Kannada typed in English letters.
# Used when the AI is unavailable, and as a second try when the AI leaves the category empty.
KEYWORDS = {
    "Water Supply": ["water", "tap", "pipe", "borewell", "bore well", "tank", "drinking", "leak",
                     "neeru", "neer", "nalli", "kudiyuva",
                     "ನೀರು", "ನೀರಿ", "ನಲ್ಲಿ", "ಪೈಪ್", "ಬೋರ್", "ಟ್ಯಾಂಕ್", "ಕುಡಿಯುವ"],
    "Electricity": ["power", "electric", "current", "streetlight", "street light", "light", "transformer",
                    "wire", "pole", "voltage", "bescom", "shock", "beedi deepa", "deepa", "karent",
                    "ವಿದ್ಯುತ್", "ಕರೆಂಟ್", "ದೀಪ", "ಲೈಟ್", "ಟ್ರಾನ್ಸ್‌ಫಾರ್ಮರ್", "ಕಂಬ", "ತಂತಿ"],
    "Roads": ["road", "pothole", "bridge", "footpath", "culvert", "highway", "street damaged",
              "rasthe", "raste", "gundi", "setuve",
              "ರಸ್ತೆ", "ಗುಂಡಿ", "ಸೇತುವೆ", "ಹಾದಿ", "ಡಾಂಬರು"],
    "Sanitation": ["garbage", "drain", "toilet", "sewage", "waste", "dustbin", "smell", "mosquito",
                   "gutter", "kasa", "charandi", "shouchalaya",
                   "ಕಸ", "ಚರಂಡಿ", "ಶೌಚಾಲಯ", "ಗಬ್ಬು", "ಸೊಳ್ಳೆ", "ಕೊಳಚೆ"],
    "Land Records": ["land", "rtc", "pahani", "khata", "survey", "mutation", "record", "boundary",
                     "property", "jameenu", "jamin", "hola",
                     "ಜಮೀನು", "ಪಹಣಿ", "ಖಾತೆ", "ಸರ್ವೆ", "ಹೊಲ", "ಆಸ್ತಿ"],
    "Stray Animals": ["dog", "dogs", "stray", "monkey", "cattle", "cow", "snake", "animal", "bite",
                      "naayi", "nayi", "kothi", "dana", "haavu",
                      "ನಾಯಿ", "ಕೋತಿ", "ದನ", "ಹಸು", "ಹಾವು", "ಪ್ರಾಣಿ"],
}


def infer_category(text):
    """The category whose keywords appear most often in the text, or None."""
    low = (text or "").lower()
    scores = {c: sum(1 for w in words if w in low) for c, words in KEYWORDS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else None


def keyword_fallback(text):
    low = (text or "").lower()
    category = infer_category(text)
    village = next((v for v in VILLAGES if v.lower() in low or VILLAGE_KN[v] in text), None)
    is_kn = any("ಀ" <= ch <= "೿" for ch in text or "")
    return {"is_grievance": True, "category": category, "village": village,
            "summary_en": (text or "Photo complaint")[:200], "summary_kn": None,
            "language": "kn" if is_kn else "en",
            "confidence": 0.65 if category else 0.0, "sensitive": False}


VILLAGE_HINTS = ", ".join(f"{v} ({VILLAGE_KN[v]})" for v in VILLAGES)

SYSTEM_PROMPT = f"""You are the intake classifier for a public grievance redressal service in rural Karnataka.
Citizens send complaints as text, voice-note transcripts (often messy, Kannada, English, or mixed,
sometimes with speech-to-text errors), or photos with an optional caption.

Extract structured fields by calling the record_complaint tool. Rules:
- category: exactly one of {", ".join(CATEGORIES)}. Use null if you cannot tell.
  Photos count as evidence: a broken pipe is Water Supply, a dark or broken streetlight is Electricity,
  a pothole is Roads, garbage or a blocked drain is Sanitation.
- village: exactly one of {VILLAGE_HINTS}. Return the English name. Match Kannada spellings and
  close misspellings. Use null if no known village is named. Never guess.
- summary_en / summary_kn: one short, neutral sentence describing the problem, in English and in Kannada.
- language: "kn" if the citizen wrote or spoke mainly Kannada, otherwise "en".
- confidence: 0 to 1, how sure you are about the category and the summary together.
- sensitive: true for harassment, caste, land disputes between people, or complaints against a named person.
- is_grievance: false for greetings, forwards, political messages, jokes, or anything that is not a
  civic complaint. When false, the other fields may be null.
"""

TOOL = {
    "name": "record_complaint",
    "description": "Record the structured fields of a citizen complaint.",
    "input_schema": {
        "type": "object",
        "properties": {
            "is_grievance": {"type": "boolean"},
            "category": {"type": ["string", "null"], "enum": CATEGORIES + [None]},
            "village": {"type": ["string", "null"], "enum": VILLAGES + [None]},
            "summary_en": {"type": ["string", "null"]},
            "summary_kn": {"type": ["string", "null"]},
            "language": {"type": "string", "enum": ["kn", "en"]},
            "confidence": {"type": "number"},
            "sensitive": {"type": "boolean"},
        },
        "required": ["is_grievance", "category", "village", "summary_en", "summary_kn",
                     "language", "confidence", "sensitive"],
    },
}


def classify_complaint(text: str = "", image_bytes: bytes = None, image_type="image/jpeg") -> dict:
    content = []
    if image_bytes:
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": image_type,
                       "data": base64.b64encode(image_bytes).decode()},
        })
    content.append({"type": "text", "text": text or "(photo with no caption)"})

    try:
        response = get_client().messages.create(
            model=MODEL,
            max_tokens=600,
            system=SYSTEM_PROMPT,
            tools=[TOOL],
            tool_choice={"type": "tool", "name": "record_complaint"},
            messages=[{"role": "user", "content": content}],
        )
        data = next(b.input for b in response.content if b.type == "tool_use")
    except Exception as exc:  # network or API failure: fall back to a human
        print(f"[classifier] AI unavailable, using keyword fallback: {exc}")
        data = keyword_fallback(text)

    if data.get("category") not in CATEGORIES:
        data["category"] = None
    if data.get("village") not in VILLAGES:
        data["village"] = None
    data["confidence"] = float(data.get("confidence") or 0)
    return data
