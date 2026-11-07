from .catalog import destination_catalog

DEFAULT_PLANNING_BUDGET = 12000
DEFAULT_TRIP_DAYS = 3
RECOMMENDATION_LIMIT = 3
INTEREST_TERMS = {
    "historical places": (
        "historic",
        "heritage",
        "old city",
        "palace",
        "monument",
        "fort",
        "canyon",
        "caves",
    ),
    "beach destinations": ("beach", "coastal", "coast", "lagoon"),
    "nature and hill stations": (
        "garden",
        "mountain",
        "alpine",
        "rice terraces",
        "park",
        "canyon",
        "gorge",
        "caves",
    ),
    "adventure activities": ("safari", "trek", "adventure", "watersports", "canyon"),
    "family-friendly options": ("family", "garden", "museum", "park", "temple"),
    "food experiences": (
        "food",
        "cuisine",
        "dining",
        "culinary",
        "bazaar",
        "rayalaseema",
    ),
    "culture and heritage": (
        "temple",
        "heritage",
        "historic",
        "museum",
        "cultural",
        "palace",
        "dargah",
    ),
    "nightlife": ("nightlife", "bars", "clubs", "marina"),
}


def preference_match_score(highlights, preferences):
    text = highlights.lower()
    return sum(
        any(term in text for term in INTEREST_TERMS.get(preference, ()))
        for preference in preferences
    )


def _estimate(profile, days, budget, preferences):
    nights = max(0, days - 1)
    hotel_cost = profile["hotel_night"] * nights
    total = profile["flight_cost"] + hotel_cost + profile["daily_cost"] * days
    return {
        **profile,
        "trip_length": "%d days" % days,
        "hotel_cost": hotel_cost,
        "estimated_total": total,
        "within_budget": total <= budget,
        "style_score": preference_match_score(profile["highlights"], preferences),
    }


def build_local_recommendations(preferences):
    budget = preferences.get("budget") or DEFAULT_PLANNING_BUDGET
    days = preferences.get("days") or DEFAULT_TRIP_DAYS
    interests = preferences.get("preferences") or []
    catalog = destination_catalog()
    destination = preferences.get("destination")
    if destination:
        profile = catalog.get(destination)
        return [_estimate(profile, days, budget, interests)] if profile else []
    ranked = [
        _estimate(profile, days, budget, interests)
        for profile in catalog.of_type(preferences.get("trip_type", "domestic"))
    ]
    ranked.sort(
        key=lambda item: (
            not item["within_budget"],
            -item["style_score"],
            item["estimated_total"],
        )
    )
    if interests:
        suited = ", ".join(interests[:2])
        for item in ranked:
            item["highlights"] = "%s; suited to %s" % (item["highlights"], suited)
    return ranked[:RECOMMENDATION_LIMIT]


def build_itinerary(destination, days):
    profile = destination_catalog().get(destination)
    if profile and "itinerary" in profile:
        plan = profile["itinerary"]
    else:
        plan = [
            "Arrive in %s, visit central historic sites and enjoy authentic local "
            "cuisine" % destination,
            "Excursion to scenic natural viewpoints, artisan bazaars, and prominent "
            "cultural heritage",
            "Local market visits, regional culinary tasting, and relaxed sightseeing "
            "before return travel",
        ]
    return [
        (
            plan[index]
            if index < len(plan)
            else "Flexible day excursion or scenic exploration in %s" % destination
        )
        for index in range(max(1, days))
    ]


def seasonal_note(destination, month):
    profile = destination_catalog().get(destination)
    if profile and "season" in profile:
        if month:
            return "%s Verify forecasts and local advisories for %s." % (
                profile["season"],
                month,
            )
        return profile["season"]
    return (
        "Check the local weather forecast and opening hours for %s before finalizing "
        "travel for %s." % (destination, month)
    )
