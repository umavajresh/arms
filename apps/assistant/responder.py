import re

from django.urls import reverse

from .faq import answer_faq
from .inventory import search_real_flights
from .llm import ProviderConfiguration, call_external_llm
from .preferences import extract_travel_preferences
from .pricing import format_flight_price_chart
from .prompts import build_grounding_context, language_directive
from .recommendations import (
    DEFAULT_PLANNING_BUDGET,
    DEFAULT_TRIP_DAYS,
    build_itinerary,
    build_local_recommendations,
    seasonal_note,
)
from .text import contains_guest_reference, detect_language

HISTORY_TURNS_FOR_MODEL = 6
HISTORY_CONTENT_LIMIT = 1200
STATUS_QUERY = re.compile(
    r"\b(?:flight status|status of (?:my )?flight|is .* on time|flight .* delayed|"
    r"flight .* landed)\b"
)
GREETING = re.compile(
    r"^(hi|hello|hey|good\s*(?:morning|afternoon|evening)|greetings|"
    r"what\s*can\s*you\s*do|who\s*are\s*you|help)\b"
)
FLIGHT_SEARCH_TERMS = ("flight", "flights", "fly", "fare", "ticket", "airfare")


class TravelResponder:
    def __init__(self, message, flights=None, language="en", travel_preferences=None):
        self.message = message or ""
        self.lowered = self.message.strip().lower()
        self.language = detect_language(self.message, language)
        self.flights = flights
        self.preferences = travel_preferences or extract_travel_preferences(
            self.message
        )

    def respond(self, session_context=None, api_key=None, provider=None, model=None):
        faq = answer_faq(self.message, language=self.language)
        if faq and STATUS_QUERY.search(self.lowered):
            return faq
        if contains_guest_reference(self.message):
            return (
                "For your privacy, I cannot look up booking details in chat. Use the "
                "[Guest Booking Lookup](%s) portal and complete its passenger "
                "verification." % reverse("bookings:guest-lookup")
            )
        if ProviderConfiguration.resolve(api_key, provider).key:
            reply = call_external_llm(
                messages=self.model_messages(session_context),
                api_key=api_key,
                provider=provider,
                model=model,
            )
            if reply:
                return reply
        return faq or self.local_response()

    def model_messages(self, session_context):
        system = build_grounding_context(self.flights, self.preferences)
        messages = [
            {"role": "system", "content": system + language_directive(self.language)}
        ]
        for turn in (session_context or [])[-HISTORY_TURNS_FOR_MODEL:]:
            if (
                isinstance(turn, dict)
                and turn.get("role") in ("user", "assistant")
                and isinstance(turn.get("content"), str)
            ):
                messages.append(
                    {
                        "role": turn["role"],
                        "content": turn["content"][:HISTORY_CONTENT_LIMIT],
                    }
                )
        messages.append({"role": "user", "content": self.message})
        return messages

    def local_response(self):
        budget = self.preferences.get("budget")
        destination = self.preferences.get("destination")
        if GREETING.search(self.lowered) and not budget and not destination:
            return self.greeting()
        if self.is_flight_search() and not budget:
            return self.flight_search()
        recommendations = build_local_recommendations(self.preferences)
        if destination and not recommendations:
            return self.unknown_destination(destination)
        return self.trip_plan(recommendations)

    def matching_flights(self, limit):
        if self.flights is not None:
            return self.flights
        return search_real_flights(self.preferences, limit=limit)

    def is_flight_search(self):
        mentions_flights = any(term in self.lowered for term in FLIGHT_SEARCH_TERMS)
        has_route = (
            self.preferences.get("origin")
            or self.preferences.get("destination")
            or "from" in self.lowered
            or "to" in self.lowered
        )
        return mentions_flights and bool(has_route)

    def greeting(self):
        if self.language == "es":
            return (
                "Hola. Bienvenido al Asistente de Viajes ARMS 2.0. "
                "Puedo buscar horarios guardados en ARMS, preparar estimaciones de "
                "viaje y dirigirle a la aerolínea para confirmar políticas vigentes. "
                "Para consultar una reserva, use el portal seguro de búsqueda de "
                "invitados. ¿A dónde planea viajar?"
            )
        return "\n".join(
            [
                "Hello. Welcome to the ARMS 2.0 Intelligent Aviation & Travel "
                "Concierge.",
                "I can assist you with:",
                "- Searching scheduled flights and seat availability recorded in the "
                "ARMS inventory",
                "- Designing custom itineraries and clearly labeled planning "
                "estimates",
                "- Explaining where to confirm carrier-specific baggage and check-in "
                "rules",
                "- Managing a reservation through the verified guest lookup portal",
                "",
                "To get started, you can try asking:",
                "- 'Plan a trip to Kadapa under ₹12,000'",
                "- 'Show me available flights from Chennai'",
                "- 'What is the baggage allowance for international flights?'",
                "- 'Plan a 3-day trip to Paris' or 'Plan a trip to Dubai'",
                "- 'Price chart for flight AI101'",
            ]
        )

    def flight_search(self):
        flights = self.matching_flights(limit=6)
        if not flights:
            origin = self.preferences.get("origin")
            destination = self.preferences.get("destination")
            route = ("from %s " % origin if origin else "") + (
                "to %s" % destination if destination else ""
            )
            return "\n".join(
                [
                    "No matching scheduled flights were found %s in ARMS inventory."
                    % route,
                    "",
                    "You can search the full flight schedule directly on our "
                    "[Flight Search Portal](%s) or try another origin and destination."
                    % reverse("flights:search"),
                ]
            )
        lines = [
            "Scheduled flight records in ARMS matching your route "
            "(not live airline availability):",
            "",
        ]
        for flight in flights:
            lines.append(
                "- %s (%s) | %s to %s | %s | Economy %s %s (%s seats available)%s"
                % (
                    flight.get("code"),
                    flight.get("airline"),
                    flight.get("from"),
                    flight.get("to"),
                    flight.get("departure"),
                    flight.get("currency", "INR"),
                    flight.get("economy_price"),
                    flight.get("economy_available", "available"),
                    self.booking_link(flight),
                )
            )
        lines.extend(["", format_flight_price_chart(flights[0]), ""])
        lines.append(
            "Select a record to review seats and submit an internal ARMS "
            "reservation request."
        )
        return "\n".join(lines)

    def unknown_destination(self, destination):
        flights = self.matching_flights(limit=5)
        lines = [
            "I do not have a verified destination guide or sample budget for %s, so "
            "I will not invent attractions, routes, or costs." % destination,
            "ARMS can only check scheduled flight records in its own inventory; those "
            "records are not live airline availability or booking offers.",
        ]
        if flights:
            lines.append("Matching scheduled records in ARMS:")
            lines.extend(
                "- %s | %s to %s | %s | %s %s (%s seats shown in ARMS)"
                % (
                    flight["code"],
                    flight["from"],
                    flight["to"],
                    flight["departure"],
                    flight["currency"],
                    flight["economy_price"],
                    flight["economy_available"],
                )
                for flight in flights[:5]
            )
        else:
            lines.append("No matching scheduled flight records were found in ARMS.")
        lines.append(
            "For current fares, destination guidance, and ticketing, verify directly "
            "with the relevant airline or travel provider."
        )
        return "\n".join(lines)

    def trip_plan(self, recommendations):
        budget = self.preferences.get("budget")
        days = self.preferences.get("days") or DEFAULT_TRIP_DAYS
        destination = self.preferences.get("destination")
        month = self.preferences.get("month")
        is_international = self.preferences.get("trip_type") == "international"
        travel_label = "international trip" if is_international else "trip"
        budget_text = "₹{:,}".format(int(budget)) if budget else "not provided"
        lines = [
            "%s plan for %d days, from %s. Budget: %s (per traveler unless specified "
            "otherwise)."
            % (
                travel_label.title(),
                days,
                self.preferences.get("origin") or "not provided",
                budget_text,
            ),
            "",
            "Sample destination guidance and cost estimates from the ARMS directory; "
            "not current market prices or booking quotes:",
        ]
        lines.extend(self.recommendation_line(item, days) for item in recommendations)
        chosen = recommendations[0]["name"] if recommendations else None
        if chosen:
            itinerary = build_itinerary(chosen, days)
            lines.extend(["", "Suggested %s itinerary:" % chosen])
            lines.extend(
                "- Day %d: %s" % (index, activity)
                for index, activity in enumerate(itinerary, 1)
            )
        if month:
            note = seasonal_note(chosen or destination or "your destination", month)
            lines.extend(
                [
                    "",
                    "Sample seasonal note for %s (verify before booking): %s"
                    % (month, note),
                ]
            )
        lines.extend(["", "Scheduled flight records currently in ARMS inventory:"])
        lines.extend(self.inventory_lines(destination))
        lines.extend(
            [
                "",
                "These are planning estimates, not booking quotes. Tell me your "
                "departure city, exact dates, and number of travelers to narrow the "
                "plan.",
            ]
        )
        return "\n".join(lines)

    def recommendation_line(self, item, days):
        if self.preferences.get("budget"):
            note = (
                "within the supplied budget"
                if item["within_budget"]
                else "over the supplied budget"
            )
        else:
            cap = "₹{:,}".format(DEFAULT_PLANNING_BUDGET)
            note = (
                "within the sample %s planning cap" % cap
                if item["within_budget"]
                else "over the sample %s planning cap" % cap
            )
        return (
            "- %s: about ₹%s total, %s (estimated transport allowance ₹%s; lodging "
            "for %d nights ~₹%s; food/local transport/activities ~₹%s). %s"
            % (
                item["name"],
                "{:,}".format(item["estimated_total"]),
                note,
                "{:,}".format(item["flight_cost"]),
                max(0, days - 1),
                "{:,}".format(item["hotel_cost"]),
                "{:,}".format(item["daily_cost"] * days),
                item["highlights"],
            )
        )

    def inventory_lines(self, destination):
        flights = self.matching_flights(limit=5) or []
        lines = []
        if destination and not any(
            destination.lower() in flight["to"].lower() for flight in flights
        ):
            lines.append(
                "- ARMS has no scheduled flight record matching %s. No nearby hub or "
                "connecting ground route has been verified." % destination
            )
        if not flights:
            lines.append(
                "- No matching scheduled flight records were found in ARMS. Try a "
                "different origin, destination, or date."
            )
            return lines
        for flight in flights[:4]:
            lines.append(
                "- %s | %s to %s | %s | economy %s %s (%s seats shown available)%s"
                % (
                    flight["code"],
                    flight["from"],
                    flight["to"],
                    flight["departure"],
                    flight["currency"],
                    flight["economy_price"],
                    flight["economy_available"],
                    self.booking_link(flight),
                )
            )
        lines.extend(["", format_flight_price_chart(flights[0])])
        return lines

    def booking_link(self, flight):
        if not flight.get("id"):
            return ""
        return " [Book Seats](%s)" % reverse(
            "bookings:seat-selection", args=[flight["id"]]
        )


def get_travel_response(
    message,
    flights=None,
    language="en",
    session_context=None,
    api_key=None,
    ai_provider=None,
    ai_model=None,
    travel_preferences=None,
):
    responder = TravelResponder(message, flights, language, travel_preferences)
    return responder.respond(session_context, api_key, ai_provider, ai_model)
