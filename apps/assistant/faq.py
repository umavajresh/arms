import re

from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from .inventory import format_moment, recorded_flights
from .pricing import format_flight_price_chart

FLIGHT_CODE_PATTERN = re.compile(r"\b([a-zA-Z]{2,4}\s*[-]?\s*\d{2,4})\b", re.IGNORECASE)
STATUS_KEYWORDS = (
    "status",
    "track",
    "flight",
    "delayed",
    "departure",
    "where is",
    "on time",
    "info",
    "vuelo",
    "flughafen",
    "état",
)
PRICE_CHART_KEYWORDS = (
    "price chart",
    "fare chart",
    "breakdown",
    "fare breakdown",
    "ticket price breakdown",
)
BAGGAGE_KEYWORDS = (
    "baggage",
    "luggage",
    "cabin bag",
    "check-in bag",
    "weight limit",
    "equipaje",
    "bagages",
    "gepäck",
)
CANCEL_KEYWORDS = ("cancel", "cancelar", "annuler", "stornieren")
CANCEL_CONTEXT_KEYWORDS = (
    "policy",
    "how",
    "booking",
    "reservation",
    "ticket",
    "refund",
    "reembolso",
    "rückerstattung",
)
CHECK_IN_KEYWORDS = (
    "check-in",
    "check in time",
    "boarding pass",
    "when should i arrive",
    "counter open",
    "airport timing",
    "facturación",
    "enregistrement",
)
BAGGAGE_ANSWERS = {
    "es": (
        "No tengo una fuente oficial de equipaje para la aerolínea de su vuelo. "
        "Consulte el sitio web de la aerolínea para conocer los límites y cargos "
        "vigentes."
    ),
    "fr": (
        "Je ne dispose pas d'une source officielle sur les bagages de votre "
        "compagnie aérienne. Consultez son site officiel pour les limites et frais "
        "en vigueur."
    ),
    "en": (
        "ARMS does not have an authoritative baggage-policy source configured for "
        "your airline. Check the operating carrier's official website for current "
        "cabin and checked baggage limits and fees."
    ),
}
CHECK_IN_ANSWER = (
    "ARMS does not have an authoritative check-in or boarding-time source "
    "configured for your carrier. Check your airline's official itinerary and "
    "airport guidance before departure."
)


def _mentions(text, keywords):
    return any(keyword in text for keyword in keywords)


def _normalize_code(match):
    return match.group(1).replace(" ", "").replace("-", "").upper()


def _schedule_phase(flight):
    now = timezone.now()
    if flight.departure > now:
        return "Scheduled departure is in the future"
    if flight.estimated_arrival > now:
        return "Scheduled arrival is in the future"
    return "Scheduled arrival time has passed"


def _aircraft_label(flight):
    if flight.aircraft is None:
        return "To be assigned"
    return "%s (%s)" % (flight.aircraft.model_name, flight.aircraft.code)


def flight_status_answer(code):
    flight = (
        recorded_flights()
        .filter(Q(code__iexact=code) | Q(code__icontains=code))
        .first()
    )
    if flight is None:
        return None
    tracker_url = "%s?flight=%s" % (reverse("tracking:tracker"), flight.code)
    seats_url = reverse("bookings:seat-selection", args=[flight.id])
    return "\n".join(
        [
            "Flight Status for %s (%s):" % (flight.code, flight.airline.name),
            "- Route: %s (%s) to %s (%s)"
            % (
                flight.from_airport.name,
                flight.from_airport.code,
                flight.to_airport.name,
                flight.to_airport.code,
            ),
            "- Scheduled Departure: %s" % format_moment(flight.departure),
            "- Scheduled Arrival: %s" % format_moment(flight.estimated_arrival),
            "- Aircraft: %s" % _aircraft_label(flight),
            "- Schedule-only phase (not live telemetry): %s" % _schedule_phase(flight),
            "- Available Seats: %s Economy, %s Business"
            % (flight.available_economy, flight.available_business),
            "- Flight Tracker (provider-dependent): [Open Tracker](%s)" % tracker_url,
            "- Book Seats: [Select Seats](%s)" % seats_url,
        ]
    )


def price_chart_answer(code):
    if not code:
        return (
            "Please provide a flight code so I can look up its fare in ARMS inventory."
        )
    flight = recorded_flights().filter(code__iexact=code).first()
    if flight is None:
        return (
            "No matching flight fare is recorded in ARMS inventory, so I cannot "
            "provide a fare breakdown. Search scheduled flight records to see "
            "available ARMS inventory."
        )
    chart = format_flight_price_chart(
        {
            "code": flight.code,
            "economy_price": flight.economy_price,
            "business_price": flight.business_class_price,
            "currency": flight.currency,
        }
    )
    seats_url = reverse("bookings:seat-selection", args=[flight.id])
    return "\n".join(
        [
            chart,
            "",
            "- Interactive Seat Booking: [Select Seats for %s](%s)"
            % (flight.code, seats_url),
        ]
    )


def cancellation_answer(language):
    my_bookings = reverse("bookings:my-reservations")
    guest_lookup = reverse("bookings:guest-lookup")
    if language == "es":
        return (
            "Puede gestionar una reserva de ARMS en [Mis Reservas](%s) o en "
            "[Consulta de reserva de invitado](%s). Esto solo actualiza el registro "
            "de ARMS; verifique las cancelaciones y reembolsos de reservas externas "
            "con la aerolínea." % (my_bookings, guest_lookup)
        )
    return (
        "You can manage an ARMS record through [My Bookings](%s) or "
        "[Guest Booking Lookup](%s). This only updates the ARMS record. "
        "Check the operating carrier's official policy for external booking "
        "cancellations and refunds." % (my_bookings, guest_lookup)
    )


def answer_faq(message, language="en"):
    lowered = (message or "").strip().lower()
    code_match = FLIGHT_CODE_PATTERN.search(message or "")
    if code_match and _mentions(lowered, STATUS_KEYWORDS):
        status = flight_status_answer(_normalize_code(code_match))
        if status:
            return status
    if _mentions(lowered, PRICE_CHART_KEYWORDS):
        return price_chart_answer(_normalize_code(code_match) if code_match else "")
    if _mentions(lowered, BAGGAGE_KEYWORDS):
        return BAGGAGE_ANSWERS.get(language, BAGGAGE_ANSWERS["en"])
    if _mentions(lowered, CANCEL_KEYWORDS) and _mentions(
        lowered, CANCEL_CONTEXT_KEYWORDS
    ):
        return cancellation_answer(language)
    if _mentions(lowered, CHECK_IN_KEYWORDS):
        return CHECK_IN_ANSWER
    return None
