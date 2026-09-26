"""
All citizen-facing text, in Kannada (kn) and English (en).
Ask a native Kannada speaker to check every kn string before the demo.
Officer-facing text is English only (kept in bot.py).
"""

TEXT = {
    "choose_language": {
        "kn": "ನಮಸ್ಕಾರ! ಜನಸೇವೆ ಕುಂದುಕೊರತೆ ಸೇವೆಗೆ ಸ್ವಾಗತ.\nದಯವಿಟ್ಟು ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ / Please choose a language:",
        "en": "Welcome to the Janaseva grievance service.\nPlease choose a language / ದಯವಿಟ್ಟು ಭಾಷೆ ಆಯ್ಕೆಮಾಡಿ:",
    },
    "privacy_notice": {
        "kn": (
            "🔒 ಗೌಪ್ಯತೆ ಸೂಚನೆ\n"
            "ನಿಮ್ಮ ದೂರನ್ನು ಸರಿಯಾದ ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಲು ನಾವು ನಿಮ್ಮ ಹೆಸರು, ಫೋನ್ ಸಂಖ್ಯೆ, ಗ್ರಾಮ ಮತ್ತು ದೂರಿನ ವಿವರ "
            "(ಧ್ವನಿ/ಫೋಟೋ ಸೇರಿ) ಸಂಗ್ರಹಿಸುತ್ತೇವೆ.\n"
            "• ನಿಯೋಜಿತ ಅಧಿಕಾರಿ ಮಾತ್ರ ನಿಮ್ಮ ವಿವರ ನೋಡುತ್ತಾರೆ.\n"
            "• ಪ್ರಕರಣ ಮುಗಿದ 1 ವರ್ಷದ ನಂತರ ವೈಯಕ್ತಿಕ ವಿವರ ಅಳಿಸಲಾಗುತ್ತದೆ.\n"
            "• ಯಾವಾಗ ಬೇಕಾದರೂ /stopdata ಕಳುಹಿಸಿ ಒಪ್ಪಿಗೆ ಹಿಂಪಡೆಯಬಹುದು.\n\n"
            "ನೀವು ಒಪ್ಪುತ್ತೀರಾ?"
        ),
        "en": (
            "🔒 Privacy notice\n"
            "To send your complaint to the right officer, we collect your name, phone number, village and "
            "complaint details (including voice notes and photos).\n"
            "• Only the assigned officer sees your details.\n"
            "• Personal details are deleted 1 year after your case closes.\n"
            "• Send /stopdata at any time to withdraw consent.\n\n"
            "Do you agree?"
        ),
    },
    "agree": {"kn": "✅ ಒಪ್ಪುತ್ತೇನೆ", "en": "✅ I agree"},
    "disagree": {"kn": "❌ ಒಪ್ಪುವುದಿಲ್ಲ", "en": "❌ I don't agree"},
    "no_consent": {
        "kn": "ಸರಿ. ನಿಮ್ಮ ಯಾವುದೇ ವಿವರವನ್ನು ನಾವು ಸಂಗ್ರಹಿಸಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಾರಂಭಿಸಲು /start ಕಳುಹಿಸಿ.",
        "en": "Okay. We have not stored any of your details. Send /start to begin again.",
    },
    "ask_name": {"kn": "ನಿಮ್ಮ ಹೆಸರು ಏನು?", "en": "What is your name?"},
    "ready": {
        "kn": "ಧನ್ಯವಾದಗಳು {name}. ಈಗ ನಿಮ್ಮ ಸಮಸ್ಯೆಯನ್ನು ಬರೆಯಿರಿ, ಧ್ವನಿ ಸಂದೇಶ ಕಳುಹಿಸಿ, ಅಥವಾ ಫೋಟೋ ಕಳುಹಿಸಿ.",
        "en": "Thank you, {name}. Now describe your problem: type it, send a voice note, or send a photo.",
    },
    "processing": {"kn": "⏳ ನಿಮ್ಮ ದೂರನ್ನು ಅರ್ಥಮಾಡಿಕೊಳ್ಳುತ್ತಿದ್ದೇವೆ...", "en": "⏳ Understanding your complaint..."},
    "heard": {"kn": "🎙️ ನಾವು ಕೇಳಿದ್ದು: “{text}”", "en": "🎙️ We heard: “{text}”"},
    "not_grievance": {
        "kn": "🙏 ಈ ಸಂಖ್ಯೆ ಸಾರ್ವಜನಿಕ ದೂರುಗಳಿಗೆ ಮಾತ್ರ. ನಿಮ್ಮ ಗ್ರಾಮದ ಸಮಸ್ಯೆಯನ್ನು ಬರೆಯಿರಿ ಅಥವಾ ಧ್ವನಿ ಸಂದೇಶ ಕಳುಹಿಸಿ.",
        "en": "🙏 This number is only for public complaints. Please describe a problem in your village.",
    },
    "ask_village": {"kn": "📍 ಇದು ಯಾವ ಗ್ರಾಮದಲ್ಲಿ? ಕೆಳಗೆ ಒತ್ತಿ, ಅಥವಾ ಗ್ರಾಮದ ಹೆಸರು ಬರೆಯಿರಿ.",
                    "en": "📍 Which village is this in? Tap one below, or type the village name."},
    "ask_category": {"kn": "📂 ಇದು ಯಾವ ರೀತಿಯ ಸಮಸ್ಯೆ? ಕೆಳಗೆ ಒತ್ತಿ, ಅಥವಾ ನಿಮ್ಮ ಮಾತಿನಲ್ಲಿ ಬರೆಯಿರಿ.",
                     "en": "📂 What type of problem is this? Tap one below, or type it in your own words."},
    "not_sure": {"kn": "🤷 ಗೊತ್ತಿಲ್ಲ", "en": "🤷 Not sure"},
    "describe_village": {
        "kn": "✏️ ಪರವಾಗಿಲ್ಲ. ಹತ್ತಿರದ ಊರು, ಬಡಾವಣೆ ಅಥವಾ ಗುರುತಿನ ಸ್ಥಳದ ಹೆಸರು ಬರೆಯಿರಿ (ಉದಾ: ಶಾಲೆಯ ಹತ್ತಿರ, ಹೊಸಹಳ್ಳಿ ಕ್ರಾಸ್).",
        "en": "✏️ No problem. Type the nearest village, area or landmark (for example: near the school, Hosahalli cross).",
    },
    "describe_category": {
        "kn": "✏️ ಪರವಾಗಿಲ್ಲ. ಸಮಸ್ಯೆ ಯಾವುದರ ಬಗ್ಗೆ ಎಂದು ನಿಮ್ಮ ಮಾತಿನಲ್ಲಿ ಬರೆಯಿರಿ (ಉದಾ: ನಾಯಿ ಕಾಟ, ನೀರು ಬರುತ್ತಿಲ್ಲ).",
        "en": "✏️ No problem. Type what the problem is about, in your own words (for example: stray dogs, no water).",
    },
    "skip": {"kn": "⏭ ಬಿಟ್ಟುಬಿಡಿ", "en": "⏭ Skip"},
    "spam_marked": {
        "kn": "🚫 ನಿಮ್ಮ ದೂರು {tid} ಅನ್ನು ಅಧಿಕಾರಿ ನಿಜವಲ್ಲದ ದೂರು ಎಂದು ಗುರುತಿಸಿದ್ದಾರೆ.\nಕಾರಣ: {reason}",
        "en": "🚫 The officer marked your complaint {tid} as not genuine.\nReason: {reason}",
    },
    "spam_fake": {"kn": "ನಕಲಿ / ನಿಜವಾದ ಸಮಸ್ಯೆಯಲ್ಲ", "en": "Fake / not a real problem"},
    "spam_abusive": {"kn": "ಅವಾಚ್ಯ ಭಾಷೆ", "en": "Abusive language"},
    "spam_duplicate": {"kn": "ಇನ್ನೊಂದು ದೂರಿನ ಪುನರಾವರ್ತನೆ", "en": "Duplicate of another complaint"},
    "spam_irrelevant": {"kn": "ದೂರು ಅಲ್ಲ (ತಮಾಷೆ, ಜಾಹೀರಾತು, ಫಾರ್ವರ್ಡ್)", "en": "Not a complaint (joke, ad, forward)"},
    "spam_warning": {
        "kn": "⚠️ ಎಚ್ಚರಿಕೆ {n}/{max}: {max} ಬಾರಿ ಹೀಗೆ ಗುರುತಿಸಿದರೆ, ನೀವು ಸ್ವಲ್ಪ ಸಮಯ ದೂರು ನೀಡಲು ಸಾಧ್ಯವಿಲ್ಲ.",
        "en": "⚠️ Warning {n} of {max}: at {max}, you will not be able to file complaints for a while.",
    },
    "banned": {
        "kn": "⛔ ಹಲವು ದೂರುಗಳು ನಿಜವಲ್ಲವೆಂದು ಗುರುತಿಸಲಾಗಿದೆ. {until} ವರೆಗೆ ನೀವು ಹೊಸ ದೂರು ನೀಡಲು ಸಾಧ್ಯವಿಲ್ಲ.",
        "en": "⛔ Too many of your complaints were marked as not genuine. You cannot file new complaints until {until}.",
    },
    "banned_notice": {
        "kn": "⛔ {until} ವರೆಗೆ ನೀವು ಹೊಸ ದೂರು ನೀಡಲು ಸಾಧ್ಯವಿಲ್ಲ. ತುರ್ತು ಸಮಸ್ಯೆಗೆ ದಯವಿಟ್ಟು ಗ್ರಾಮ ಪಂಚಾಯಿತಿ ಕಚೇರಿಯನ್ನು ಸಂಪರ್ಕಿಸಿ.",
        "en": "⛔ You cannot file new complaints until {until}. For an urgent problem, please contact the Gram Panchayat office.",
    },
    "ban_lifted": {"kn": "✅ ನೀವು ಮತ್ತೆ ದೂರು ನೀಡಬಹುದು.", "en": "✅ You can file complaints again."},
    "appeal_hint": {
        "kn": "ಇದು ತಪ್ಪು ಎಂದು ನಿಮಗೆ ಅನಿಸಿದರೆ, ಕಳುಹಿಸಿ: /appeal {tid}",
        "en": "If you think this is wrong, send: /appeal {tid}",
    },
    "appeal_usage": {
        "kn": "ಬಳಕೆ: /appeal GRV-KNK-XXXXX (ನಿಜವಲ್ಲ ಎಂದು ಗುರುತಿಸಿದ ನಿಮ್ಮ ದೂರು ಮಾತ್ರ)",
        "en": "Usage: /appeal GRV-KNK-XXXXX (only for your complaints marked as not genuine)",
    },
    "appeal_done": {"kn": "ಈ ದೂರಿಗೆ ಈಗಾಗಲೇ ಮೇಲ್ಮನವಿ ಸಲ್ಲಿಸಲಾಗಿದೆ.", "en": "You have already appealed this complaint."},
    "appeal_sent": {
        "kn": "⚖️ {tid}: ನಿಮ್ಮ ಮೇಲ್ಮನವಿಯನ್ನು ಹಿರಿಯ ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ. ನಿರ್ಧಾರವನ್ನು ತಿಳಿಸುತ್ತೇವೆ.",
        "en": "⚖️ {tid}: your appeal was sent to the senior officer. We will tell you the decision.",
    },
    "appeal_ok": {
        "kn": "✅ {tid}: ಮೇಲ್ಮನವಿ ಸ್ವೀಕರಿಸಲಾಗಿದೆ. ನಿಮ್ಮ ದೂರು ಮತ್ತೆ ತೆರೆಯಲಾಗಿದೆ ಮತ್ತು ಎಚ್ಚರಿಕೆಯನ್ನು ತೆಗೆದುಹಾಕಲಾಗಿದೆ.",
        "en": "✅ {tid}: your appeal was accepted. Your complaint is open again and the warning is removed.",
    },
    "appeal_no": {
        "kn": "❌ {tid}: ಮೇಲ್ಮನವಿ ತಿರಸ್ಕರಿಸಲಾಗಿದೆ. ದೂರು ನಿಜವಲ್ಲ ಎಂಬ ಗುರುತು ಉಳಿಯುತ್ತದೆ.",
        "en": "❌ {tid}: your appeal was not accepted. The complaint stays marked as not genuine.",
    },
    "ask_location": {
        "kn": "📍 ಅಧಿಕಾರಿ ಸ್ಥಳವನ್ನು ಸುಲಭವಾಗಿ ಹುಡುಕಲು, ನೀವು ಸಮಸ್ಯೆಯ ಸ್ಥಳದಲ್ಲಿದ್ದರೆ ಕೆಳಗಿನ ಬಟನ್ ಒತ್ತಿ.\n"
              "ಇಲ್ಲದಿದ್ದರೆ ಹತ್ತಿರದ ಗುರುತಿನ ಸ್ಥಳ ಬರೆಯಿರಿ, ಅಥವಾ ಬಿಟ್ಟುಬಿಡಿ.",
        "en": "📍 To help the officer find the spot: if you are at the problem location, tap the button below.\n"
              "Or type a nearby landmark, or tap Skip.",
    },
    "share_location": {"kn": "📍 ನನ್ನ ಸ್ಥಳ ಕಳುಹಿಸಿ", "en": "📍 Send my location"},
    "loc_saved": {"kn": "📍 ಸ್ಥಳ ದಾಖಲಾಗಿದೆ.", "en": "📍 Location saved."},
    "loc_first": {"kn": "📍 ಸ್ಥಳ ದಾಖಲಾಗಿದೆ. ಈಗ ಸಮಸ್ಯೆಯನ್ನು ಬರೆಯಿರಿ ಅಥವಾ ಧ್ವನಿ/ಫೋಟೋ ಕಳುಹಿಸಿ.",
                  "en": "📍 Location saved. Now describe the problem: text, voice note or photo."},
    "loc_pin": {"kn": "ನಕ್ಷೆಯ ಗುರುತು ಬಂದಿದೆ ✅", "en": "Map pin received ✅"},
    "loc_photo": {"kn": "ಫೋಟೋದಿಂದ ಪಡೆಯಲಾಗಿದೆ ✅", "en": "Taken from the photo ✅"},
    "loc_none": {"kn": "ನೀಡಿಲ್ಲ", "en": "Not given"},
    "confirm": {
        "kn": "ದಯವಿಟ್ಟು ಪರಿಶೀಲಿಸಿ:\n\n📍 ಗ್ರಾಮ: {village}\n📂 ವಿಭಾಗ: {category}\n📝 ಸಮಸ್ಯೆ: {summary}\n📌 ಸ್ಥಳ: {location}\n👤 ಅಧಿಕಾರಿ: {post}\n\nಇದು ಸರಿಯೇ?",
        "en": "Please check:\n\n📍 Village: {village}\n📂 Category: {category}\n📝 Issue: {summary}\n📌 Location: {location}\n👤 Goes to: {post}\n\nIs this correct?",
    },
    "correct": {"kn": "✅ ಸರಿ, ಕಳುಹಿಸಿ", "en": "✅ Correct, send it"},
    "edit": {"kn": "✏️ ಬದಲಿಸಿ", "en": "✏️ Edit"},
    "filed": {
        "kn": "✅ ನಿಮ್ಮ ದೂರು ದಾಖಲಾಗಿದೆ.\nಟ್ರ್ಯಾಕಿಂಗ್ ಸಂಖ್ಯೆ: {tid}\nಕಳುಹಿಸಲಾಗಿದೆ: {post}\n\nಸ್ಥಿತಿ ತಿಳಿಯಲು: /status {tid}\n📋 ನಿಮ್ಮ ಎಲ್ಲಾ ದೂರುಗಳು: /mydashboard",
        "en": "✅ Your complaint is registered.\nTracking ID: {tid}\nSent to: {post}\n\nCheck status any time: /status {tid}\n📋 All your complaints: /mydashboard",
    },
    "filed_triage": {
        "kn": "✅ ನಿಮ್ಮ ದೂರು ದಾಖಲಾಗಿದೆ.\nಟ್ರ್ಯಾಕಿಂಗ್ ಸಂಖ್ಯೆ: {tid}\nನಮ್ಮ ತಂಡವು ಸರಿಯಾದ ಅಧಿಕಾರಿಯನ್ನು ಗುರುತಿಸಿ ಶೀಘ್ರದಲ್ಲೇ ಕಳುಹಿಸುತ್ತದೆ.",
        "en": "✅ Your complaint is registered.\nTracking ID: {tid}\nOur team will find the right officer and send it on shortly.",
    },
    "routed": {"kn": "📨 {tid}: ನಿಮ್ಮ ದೂರನ್ನು {post} ಅವರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ.", "en": "📨 {tid}: your complaint was sent to {post}."},
    "accepted": {"kn": "👍 {tid}: {post} ಅವರು ನಿಮ್ಮ ದೂರನ್ನು ಸ್ವೀಕರಿಸಿದ್ದಾರೆ.", "en": "👍 {tid}: {post} has accepted your complaint."},
    "assigned": {"kn": "📌 {tid}: ನಿಮ್ಮ ದೂರನ್ನು ಕ್ರಮಕ್ಕಾಗಿ {post} ಅವರಿಗೆ ವಹಿಸಲಾಗಿದೆ.", "en": "📌 {tid}: your complaint was assigned to {post} for action."},
    "escalated": {"kn": "⬆️ {tid}: ನಿಮ್ಮ ದೂರನ್ನು ಹಿರಿಯ ಅಧಿಕಾರಿ {post} ಅವರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ.", "en": "⬆️ {tid}: your complaint was escalated to the senior officer, {post}."},
    "resolved": {
        "kn": "✅ ನಿಮ್ಮ ದೂರು {tid} ಬಗೆಹರಿದಿದೆ.\n{post} ಅವರು ಇದನ್ನು ಬಗೆಹರಿದಿದೆ ಎಂದು ಗುರುತಿಸಿದ್ದಾರೆ. ಈ ಫೋಟೋ ಅವರ ಪುರಾವೆ.",
        "en": "✅ Your complaint {tid} has been RESOLVED.\n{post} marked it as fixed. This photo is their proof.",
    },
    "resolved_noproof": {
        "kn": "✅ ನಿಮ್ಮ ದೂರು {tid} ಬಗೆಹರಿದಿದೆ.\n{post} ಅವರು ಇದನ್ನು ಬಗೆಹರಿದಿದೆ ಎಂದು ಗುರುತಿಸಿದ್ದಾರೆ (ಫೋಟೋ ಪುರಾವೆ ಇಲ್ಲ).",
        "en": "✅ Your complaint {tid} has been RESOLVED.\n{post} marked it as fixed (no photo proof was sent).",
    },
    "verify": {
        "kn": "🔔 {tid}: ಸಮಸ್ಯೆ ಬಗೆಹರಿದಿದ್ದರೆ, ಅಧಿಕಾರಿಗೆ 1 ರಿಂದ 5 ⭐ ಅಂಕ ನೀಡಿ. ದೂರು ಮುಚ್ಚಲಾಗುತ್ತದೆ.\n"
              "ಬಗೆಹರಿದಿಲ್ಲದಿದ್ದರೆ, “ಮತ್ತೆ ತೆರೆಯಿರಿ” ಒತ್ತಿ.",
        "en": "🔔 {tid}: If the problem is fixed, rate the officer from 1 to 5 ⭐. The complaint will close.\n"
              "If it is NOT fixed, tap “Reopen”.",
    },
    "reopen_btn": {"kn": "🔁 ಬಗೆಹರಿದಿಲ್ಲ – ಮತ್ತೆ ತೆರೆಯಿರಿ", "en": "🔁 Not fixed – Reopen"},
    "post_triage": {"kn": "ನಮ್ಮ ತಂಡ ಸರಿಯಾದ ಅಧಿಕಾರಿಯನ್ನು ಆಯ್ಕೆಮಾಡುತ್ತದೆ", "en": "Our team will choose the right officer"},
    "yes": {"kn": "✅ ಹೌದು", "en": "✅ Yes"},
    "partly": {"kn": "➗ ಭಾಗಶಃ", "en": "➗ Partly"},
    "no": {"kn": "❌ ಇಲ್ಲ", "en": "❌ No"},
    "ask_rating": {"kn": "ಅಧಿಕಾರಿಯ ಸ್ಪಂದನೆಗೆ ಅಂಕ ನೀಡಿ (1 = ಕೆಟ್ಟದು, 5 = ಉತ್ತಮ):", "en": "Rate the officer's response (1 = poor, 5 = excellent):"},
    "thanks_verified": {"kn": "🙏 ಧನ್ಯವಾದಗಳು! ನಿಮ್ಮ ಅಂಕ ದಾಖಲಾಗಿದೆ. {tid} ಮುಚ್ಚಲಾಗಿದೆ.",
                        "en": "🙏 Thank you! Your rating is saved and {tid} is now closed."},
    "thanks_reopened": {"kn": "🔁 {tid} ಮತ್ತೆ ತೆರೆಯಲಾಗಿದೆ ಮತ್ತು ಅಧಿಕಾರಿಗೆ ತಿಳಿಸಲಾಗಿದೆ.", "en": "🔁 {tid} is reopened and the officer has been told."},
    "thanks_escalated": {"kn": "⬆️ {tid} ಹಿರಿಯ ಅಧಿಕಾರಿ {post} ಅವರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ.", "en": "⬆️ {tid} has gone to the senior officer, {post}."},
    "thanks_rating": {"kn": "⭐ ನಿಮ್ಮ ಅಭಿಪ್ರಾಯಕ್ಕೆ ಧನ್ಯವಾದಗಳು.", "en": "⭐ Thank you for your feedback."},
    "status_usage": {"kn": "ಬಳಕೆ: /status GRV-KNK-XXXXX", "en": "Usage: /status GRV-KNK-XXXXX"},
    "status_none": {"kn": "ಈ ಸಂಖ್ಯೆಯ ದೂರು ಸಿಗಲಿಲ್ಲ.", "en": "No complaint found with that ID."},
    "stopdata_confirm": {
        "kn": "ನಿಮ್ಮ ಒಪ್ಪಿಗೆ ಹಿಂಪಡೆದು ವೈಯಕ್ತಿಕ ವಿವರ ಅಳಿಸಬೇಕೆ? ನಿಮ್ಮ ತೆರೆದ ದೂರುಗಳು ಹೆಸರು ಇಲ್ಲದೆ ಮುಂದುವರಿಯುತ್ತವೆ.",
        "en": "Withdraw consent and delete your personal details? Your open complaints continue without your name.",
    },
    "stopdata_yes": {"kn": "ಹೌದು, ಅಳಿಸಿ", "en": "Yes, delete"},
    "stopdata_done": {"kn": "✅ ನಿಮ್ಮ ವೈಯಕ್ತಿಕ ವಿವರಗಳನ್ನು ಅಳಿಸಲಾಗಿದೆ.", "en": "✅ Your personal details have been deleted."},
    "error": {"kn": "ಕ್ಷಮಿಸಿ, ಏನೋ ತಪ್ಪಾಗಿದೆ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.", "en": "Sorry, something went wrong. Please try again."},
    "voice_failed": {"kn": "ಕ್ಷಮಿಸಿ, ಧ್ವನಿ ಸಂದೇಶ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಬರೆದು ಕಳುಹಿಸಿ.", "en": "Sorry, we could not understand the voice note. Please type your complaint."},
}

STATUS_LABEL = {
    "TRIAGE": {"kn": "ಪರಿಶೀಲನೆಯಲ್ಲಿ", "en": "Being reviewed"},
    "OPEN": {"kn": "ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ", "en": "Sent to officer"},
    "ACCEPTED": {"kn": "ಅಧಿಕಾರಿ ಸ್ವೀಕರಿಸಿದ್ದಾರೆ", "en": "Accepted by officer"},
    "ESCALATED": {"kn": "ಹಿರಿಯ ಅಧಿಕಾರಿಗೆ ಕಳುಹಿಸಲಾಗಿದೆ", "en": "Escalated to senior officer"},
    "RESOLVED_PENDING": {"kn": "ಬಗೆಹರಿದಿದೆ – ನಿಮ್ಮ ದೃಢೀಕರಣ ಬೇಕು", "en": "Resolved – waiting for your confirmation"},
    "REOPENED": {"kn": "ಮತ್ತೆ ತೆರೆಯಲಾಗಿದೆ", "en": "Reopened"},
    "VERIFIED": {"kn": "ಬಗೆಹರಿದಿದೆ (ನೀವು ದೃಢೀಕರಿಸಿದ್ದೀರಿ)", "en": "Resolved (confirmed by you)"},
    "RESOLVED_UNVERIFIED": {"kn": "ಬಗೆಹರಿದಿದೆ (ದೃಢೀಕರಿಸಿಲ್ಲ)", "en": "Resolved (not confirmed)"},
    "REJECTED": {"kn": "ನಿಜವಲ್ಲದ ದೂರು ಎಂದು ಗುರುತಿಸಲಾಗಿದೆ", "en": "Marked as not genuine"},
}


def t(lang, key, **kwargs):
    entry = TEXT[key]
    return entry.get(lang, entry["en"]).format(**kwargs)
