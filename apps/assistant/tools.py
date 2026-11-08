import math
import re

from apps.bookings.guest_access import GUEST_REFERENCE_PATTERN
from apps.bookings.models import Reservation

from .inventory import (
    airport_matches,
    bookable_flights,
    format_moment,
    recorded_flights,
)
from .pricing import compute_price_breakdown

FLIGHT_CODE_PATTERN = re.compile(r"[A-Za-z0-9-]{1,32}")
SEARCH_RESULT_LIMIT = 5


class ToolInputError(Exception):
    pass


class TravelTool:
    name = ""
    description = ""
    parameters = {}
    exposed_to_model = True

    @property
    def allowed_arguments(self):
        return set(self.parameters.get("properties", {}))

    def definition(self):
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    def run(self, arguments):
        raise NotImplementedError


class SearchFlightsTool(TravelTool):
    name = "search_flights"
    description = (
        "Search scheduled flights and seat counts recorded in ARMS inventory. "
        "Give origin and destination as city names (for example Paris) or "
        "airport codes (for example CDG). This is not live airline availability."
    )
    parameters = {
        "type": "object",
        "properties": {
            "origin": {"type": "string", "maxLength": 100},
            "destination": {"type": "string", "maxLength": 100},
            "max_price": {"type": "number", "exclusiveMinimum": 0},
        },
        "additionalProperties": False,
    }

    def run(self, arguments):
        origin = arguments.get("origin", "")
        destination = arguments.get("destination", "")
        if not isinstance(origin, str) or not isinstance(destination, str):
            raise ToolInputError("Origin and destination must be text.")
        origin, destination = origin.strip(), destination.strip()
        if len(origin) > 100 or len(destination) > 100:
            raise ToolInputError(
                "Origin and destination must be 100 characters or fewer."
            )
        flights = bookable_flights()
        if origin:
            flights = flights.filter(airport_matches("from_airport", origin))
        if destination:
            flights = flights.filter(airport_matches("to_airport", destination))
        if arguments.get("max_price") is not None:
            flights = flights.filter(
                economy_price__lte=self._positive_price(arguments["max_price"])
            )
        return [
            {
                "id": flight.id,
                "code": flight.code,
                "airline": flight.airline.name,
                "from": "%s - %s"
                % (flight.from_airport.code, flight.from_airport.name),
                "to": "%s - %s" % (flight.to_airport.code, flight.to_airport.name),
                "departure": format_moment(flight.departure),
                "economy_price": float(flight.economy_price),
                "currency": flight.currency,
                "available_seats": flight.available_economy,
            }
            for flight in flights[:SEARCH_RESULT_LIMIT]
        ]

    def _positive_price(self, value):
        try:
            price = float(value)
        except (TypeError, ValueError) as error:
            raise ToolInputError("Maximum price must be a positive number.") from error
        if not math.isfinite(price) or price <= 0:
            raise ToolInputError("Maximum price must be a positive finite number.")
        return price


class FlightDetailsTool(TravelTool):
    name = "get_flight_details"
    description = "Get a scheduled flight record from ARMS inventory."
    parameters = {
        "type": "object",
        "properties": {"code": {"type": "string", "maxLength": 32}},
        "required": ["code"],
        "additionalProperties": False,
    }

    def run(self, arguments):
        code = arguments.get("code")
        if not isinstance(code, str) or not FLIGHT_CODE_PATTERN.fullmatch(code.strip()):
            raise ToolInputError("A valid flight code is required.")
        code = code.strip().upper()
        flight = recorded_flights().filter(code__iexact=code).first()
        if flight is None:
            raise ToolInputError("Flight %s not found in ARMS inventory." % code)
        aircraft = flight.aircraft
        return {
            "id": flight.id,
            "code": flight.code,
            "airline": flight.airline.name,
            "departure": format_moment(flight.departure),
            "arrival": format_moment(flight.estimated_arrival),
            "route": "%s -> %s" % (flight.from_airport.name, flight.to_airport.name),
            "aircraft": (
                "%s (%s)" % (aircraft.model_name, aircraft.code) if aircraft else ""
            ),
            "economy_price": float(flight.economy_price),
            "business_price": float(flight.business_class_price),
            "currency": flight.currency,
            "available_economy": flight.available_economy,
            "available_business": flight.available_business,
        }


class PriceChartTool(TravelTool):
    name = "get_price_chart"
    description = (
        "Get the recorded ARMS fare and an explicitly illustrative price breakdown."
    )
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string", "maxLength": 32},
            "id": {"type": "integer", "minimum": 1},
        },
        "additionalProperties": False,
    }

    def definition(self):
        definition = super().definition()
        definition["function"]["parameters"] = {
            "type": "object",
            "properties": {"code": self.parameters["properties"]["code"]},
            "required": ["code"],
            "additionalProperties": False,
        }
        return definition

    def run(self, arguments):
        code = arguments.get("code", "")
        if not isinstance(code, str) or len(code) > 32:
            raise ToolInputError("A valid flight code is required.")
        flight = self._find(code.strip().upper(), arguments.get("id"))
        if flight is None:
            raise ToolInputError("Flight not found.")
        return {
            "id": flight.id,
            "code": flight.code,
            "airline": flight.airline.name,
            "route": "%s (%s) to %s (%s)"
            % (
                flight.from_airport.name,
                flight.from_airport.code,
                flight.to_airport.name,
                flight.to_airport.code,
            ),
            "departure": format_moment(flight.departure),
            "currency": flight.currency,
            "economy": compute_price_breakdown(flight.economy_price, "economy"),
            "business": compute_price_breakdown(
                flight.business_class_price, "business"
            ),
        }

    def _find(self, code, flight_id):
        flights = recorded_flights()
        if flight_id:
            try:
                flight_id = int(flight_id)
            except (TypeError, ValueError, OverflowError) as error:
                raise ToolInputError(
                    "A valid flight identifier is required."
                ) from error
            if flight_id < 1:
                raise ToolInputError("A valid flight identifier is required.")
            flight = flights.filter(pk=flight_id).first()
            if flight is not None:
                return flight
        return flights.filter(code__iexact=code).first() if code else None


class ReservationLookupTool(TravelTool):
    name = "lookup_reservation"
    description = "Look up a guest reservation after verifying passenger details."
    parameters = {
        "type": "object",
        "properties": {
            "reference": {"type": "string"},
            "email": {"type": "string"},
            "last_name": {"type": "string"},
        },
    }
    exposed_to_model = False

    def run(self, arguments):
        reference = arguments.get("reference")
        email = arguments.get("email")
        last_name = arguments.get("last_name")
        if not isinstance(reference, str) or not GUEST_REFERENCE_PATTERN.fullmatch(
            reference.strip().upper()
        ):
            raise ToolInputError("A valid guest booking reference is required.")
        if not isinstance(email, str) or not isinstance(last_name, str):
            raise ToolInputError("Booking reference, email, and surname are required.")
        email, last_name = email.strip().casefold(), last_name.strip().casefold()
        if not email or len(email) > 254 or not last_name or len(last_name) > 150:
            raise ToolInputError("Booking reference, email, and surname are required.")
        reservation = next(
            (
                candidate
                for candidate in Reservation.objects.with_flight().filter(
                    booking_reference=reference.strip().upper()
                )
                if candidate.email.casefold() == email
                and candidate.last_name.casefold() == last_name
            ),
            None,
        )
        if reservation is None:
            raise ToolInputError("Invalid booking reference or passenger verification.")
        flight = reservation.flight
        return {
            "reference": reservation.booking_reference,
            "passenger": "%s %s" % (reservation.first_name, reservation.last_name),
            "flight_code": flight.code,
            "route": "%s to %s" % (flight.from_airport.name, flight.to_airport.name),
            "departure": format_moment(flight.departure),
            "seat_number": reservation.seat_number,
            "status": reservation.status_label,
            "can_cancel": reservation.can_cancel,
        }


class TravelToolRegistry:
    def __init__(self, tools):
        self.tools = {tool.name: tool for tool in tools}

    def model_definitions(self):
        return [
            tool.definition() for tool in self.tools.values() if tool.exposed_to_model
        ]

    def model_tool_names(self):
        return {name for name, tool in self.tools.items() if tool.exposed_to_model}

    def execute(self, name, arguments):
        tool = self.tools.get(name)
        if tool is None:
            return {"error": "Unsupported travel tool."}
        if not isinstance(arguments, dict):
            return {"error": "Tool arguments must be an object."}
        if set(arguments) - tool.allowed_arguments:
            return {"error": "Tool arguments contain unsupported fields."}
        try:
            return tool.run(arguments)
        except ToolInputError as error:
            return {"error": str(error)}


travel_tools = TravelToolRegistry(
    [
        SearchFlightsTool(),
        FlightDetailsTool(),
        PriceChartTool(),
        ReservationLookupTool(),
    ]
)


def execute_travel_tool(name, arguments=None):
    return travel_tools.execute(name, arguments)
