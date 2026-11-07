import re

SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ja": "Japanese",
    "hi": "Hindi",
}

LANGUAGE_HINTS = (
    ("es", ("hola", "buenos días", "gracias", "viaje", "equipaje")),
    ("fr", ("bonjour", "salut", "merci", "voyage")),
    ("de", ("hallo", "guten tag", "danke", "flug")),
    ("ja", ("こんにちは", "ありがとう", "フライト")),
    ("hi", ("नमस्ते", "धन्यवाद", "यात्रा", "उड़ान")),
)

GUEST_REFERENCE_IN_TEXT = re.compile(
    r"\bGUEST-[A-Z0-9]{4}-[A-Z0-9]{4}\b", re.IGNORECASE
)


def sanitize_text(text):
    if not text:
        return ""
    cleaned = text.replace("—", ", ").replace("–", "-")
    cleaned = re.sub(r"[\U00010000-\U0010ffff]", "", cleaned)
    return re.sub(r"[☀-➿]", "", cleaned)


def detect_language(message, requested="en"):
    if requested != "en":
        return requested
    lowered = (message or "").lower()
    for language, hints in LANGUAGE_HINTS:
        if any(hint in lowered for hint in hints):
            return language
    return requested


def contains_guest_reference(message):
    return bool(GUEST_REFERENCE_IN_TEXT.search(message or ""))
