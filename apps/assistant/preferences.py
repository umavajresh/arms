import re

from .catalog import destination_catalog

BUDGET_PATTERNS = (
    r"budget(?: is| of)?\s*(?:₹|rs|inr)?\s*\d[\d,]*(?:\.\d+)?",
    r"(?:₹|rs|inr)\s*\d[\d,]*(?:\.\d+)?",
    r"under\s*(?:₹|rs|inr)?\s*\d[\d,]*(?:\.\d+)?",
)
ORIGIN_PATTERN = re.compile(
    r"\b(?:from|departing from|traveling from|travelling from)\s+"
    r"([a-z][a-z .'-]*?)(?=\s+(?:for|to|with|during|in|on)\b|[,.;!?]|$)",
    re.IGNORECASE,
)
DESTINATION_PATTERNS = (
    re.compile(
        r"\b(?:plan a trip to|plan trip to|trip to|travel to|visit|explore|"
        r"vacation in|holiday in|flights? to|going to|go to)\s+"
        r"([a-zA-Z\s'-]+?)(?=\s+(?:under|for|with|during|in|from|budget|next|this|"
        r"on|and|near)\b|[,.;!?]|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bto\s+([a-zA-Z\s'-]+?)(?=\s+(?:under|for|with|during|in|from|budget|"
        r"next|this|on)\b|[,.;!?]|$)",
        re.IGNORECASE,
    ),
)
FALLBACK_ORIGINS = (
    "chennai",
    "delhi",
    "mumbai",
    "bangalore",
    "bengaluru",
    "hyderabad",
    "kolkata",
    "london",
)
FILLER_WORDS = {"a", "an", "the", "my", "our", "some", "any"}
VAGUE_PLACES = {"here", "there", "somewhere", "anywhere"}
INTERNATIONAL_TERMS = (
    "international",
    "abroad",
    "overseas",
    "foreign trip",
    "foreign travel",
)
INTERNATIONAL_CITIES = {
    "Dubai",
    "Bangkok",
    "Singapore",
    "Bali",
    "Paris",
    "London",
    "Tokyo",
    "Kuala Lumpur",
    "Colombo",
    "Kathmandu",
    "Male",
    "New York",
    "Sydney",
    "Rome",
    "Zurich",
}
MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
INTEREST_KEYWORDS = (
    ("historical places", ("historical", "historic")),
    ("beach destinations", ("beach", "coast", "coastal")),
    ("nature and hill stations", ("nature", "hill", "mountain", "canyon", "caves")),
    ("adventure activities", ("adventure", "trek", "safari")),
    ("family-friendly options", ("family", "kids")),
    ("food experiences", ("food", "cuisine", "street food", "dining")),
    ("culture and heritage", ("culture", "museum", "heritage", "temple", "dargah")),
    ("nightlife", ("nightlife", "clubs", "bars", "party")),
)
TRIP_TYPE_TERMS = ("domestic", "international", "abroad", "overseas")
PLANNING_FIELDS = ("budget", "days", "origin", "destination", "month", "preferences")
STORED_FIELDS = (*PLANNING_FIELDS, "trip_type")


def parse_rupees(value):
    if value is None:
        return None
    cleaned = str(value).strip().lower().replace(",", "")
    for token in ("₹", "rs", "inr", "rupees", "rupee", "under", "about", "around"):
        cleaned = cleaned.replace(token, "")
    match = re.search(r"(\d+(?:\.\d+)?)", cleaned)
    return float(match.group(1)) if match else None


def extract_budget(lowered):
    for pattern in BUDGET_PATTERNS:
        match = re.search(pattern, lowered)
        if match:
            budget = parse_rupees(match.group(0))
            if budget:
                return budget
    return None


def extract_origin(text, lowered):
    match = ORIGIN_PATTERN.search(text)
    if match:
        return match.group(1).strip().title()
    for city in FALLBACK_ORIGINS:
        if "from %s" % city in lowered or "departing %s" % city in lowered:
            return city.title()
    if lowered.startswith("chennai to"):
        return "Chennai"
    return ""


def extract_destination_name(message, origin=None):
    text = (message or "").strip()
    for pattern in DESTINATION_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        words = [
            word for word in match.group(1).split() if word.lower() not in FILLER_WORDS
        ]
        candidate = " ".join(words).title()
        is_specific = candidate and candidate.lower() not in VAGUE_PLACES
        if is_specific and (not origin or candidate.lower() != origin.lower()):
            return candidate
    return destination_catalog().find_in_text(text.lower(), exclude=origin)


def infer_trip_type(lowered, destination):
    if any(term in lowered for term in INTERNATIONAL_TERMS):
        return "international"
    if destination:
        profile = destination_catalog().get(destination)
        if profile and profile["type"] == "international":
            return "international"
        if destination in INTERNATIONAL_CITIES:
            return "international"
    return "domestic"


def extract_month(lowered):
    if "next month" in lowered or "upcoming month" in lowered:
        return "next month"
    if "this month" in lowered:
        return "this month"
    return next(
        (name.title() for name in MONTHS if re.search(r"\b%s\b" % name, lowered)),
        None,
    )


def extract_interests(lowered):
    return [
        label
        for label, keywords in INTEREST_KEYWORDS
        if any(keyword in lowered for keyword in keywords)
    ]


def extract_travel_preferences(message):
    text = message or ""
    lowered = text.lower()
    days_match = re.search(r"(\d+)\s*-?\s*days?\b", lowered)
    origin = extract_origin(text, lowered)
    destination = extract_destination_name(text, origin=origin)
    return {
        "budget": extract_budget(lowered),
        "days": int(days_match.group(1)) if days_match else None,
        "origin": origin,
        "destination": destination,
        "trip_type": infer_trip_type(lowered, destination),
        "month": extract_month(lowered),
        "preferences": extract_interests(lowered),
        "message": text,
    }


def merge_with_previous(current, previous):
    previous = previous if isinstance(previous, dict) else {}
    merged = dict(current)
    for field in PLANNING_FIELDS:
        if not merged.get(field):
            merged[field] = previous.get(field)
    message = current.get("message", "").lower()
    changed_trip_type = any(term in message for term in TRIP_TYPE_TERMS)
    if (
        not changed_trip_type
        and not current.get("destination")
        and previous.get("trip_type") in ("domestic", "international")
    ):
        merged["trip_type"] = previous["trip_type"]
    if merged.get("days") is not None:
        try:
            merged["days"] = min(max(int(merged["days"]), 1), 60)
        except (TypeError, ValueError):
            merged["days"] = None
    if not isinstance(merged.get("budget"), (int, float)):
        merged["budget"] = None
    merged["preferences"] = [
        preference
        for preference in (merged.get("preferences") or [])
        if isinstance(preference, str) and len(preference) <= 80
    ][:8]
    return merged


def storable(preferences):
    return {field: preferences.get(field) for field in STORED_FIELDS}


def has_planning_context(preferences):
    return bool(
        preferences and any(preferences.get(field) for field in PLANNING_FIELDS)
    )
