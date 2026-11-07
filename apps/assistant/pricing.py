FARE_SPLITS = {
    "business": {"base_fare": 0.70, "fuel_surcharge": 0.12, "airport_fee": 0.08},
    "economy": {"base_fare": 0.68, "fuel_surcharge": 0.14, "airport_fee": 0.10},
}


def _percent(part, total):
    return round(part / total * 100) if total else 0


def compute_price_breakdown(price, seat_class="economy"):
    total = float(price or 0)
    split = FARE_SPLITS["business" if seat_class == "business" else "economy"]
    components = {name: round(total * share, 2) for name, share in split.items()}
    components["gst"] = round(total - sum(components.values()), 2)
    return {
        "total": total,
        **components,
        "base_pct": _percent(components["base_fare"], total),
        "fuel_pct": _percent(components["fuel_surcharge"], total),
        "airport_pct": _percent(components["airport_fee"], total),
        "gst_pct": _percent(components["gst"], total),
    }


def format_flight_price_chart(flight):
    code = flight.get("code", "Flight")
    currency = flight.get("currency", "INR")
    economy = compute_price_breakdown(flight.get("economy_price") or 0, "economy")
    business = compute_price_breakdown(flight.get("business_price") or 0, "business")
    return "\n".join(
        [
            "Illustrative price allocation for the ARMS-recorded fare for %s:" % code,
            "- The component split is an estimate, not an airline quote, "
            "tax calculation, or fee schedule.",
            "- Estimated base component: %s %s"
            % (currency, "{:,.2f}".format(economy["base_fare"])),
            "- Estimated fuel component: %s %s"
            % (currency, "{:,.2f}".format(economy["fuel_surcharge"])),
            "- Estimated airport component: %s %s"
            % (currency, "{:,.2f}".format(economy["airport_fee"])),
            "- Estimated tax component: %s %s"
            % (currency, "{:,.2f}".format(economy["gst"])),
            "- Economy amount recorded in ARMS: %s %s"
            % (currency, "{:,.2f}".format(economy["total"])),
            "- Business amount recorded in ARMS: %s %s"
            % (currency, "{:,.2f}".format(business["total"])),
        ]
    )
