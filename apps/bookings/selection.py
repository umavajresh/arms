import json
from dataclasses import dataclass

MAX_PASSENGERS = 6


class SeatSelectionError(Exception):
    pass


@dataclass(frozen=True)
class SeatSelection:
    flight_id: int
    seats: tuple

    @property
    def passenger_count(self):
        return len(self.seats)

    @property
    def seat_codes(self):
        return {seat.code for seat in self.seats}


def parse_seat_request(raw_payload, seat_map, occupied):
    if not raw_payload:
        raise SeatSelectionError("Please select your seats and passenger count")
    try:
        payload = json.loads(raw_payload)
    except (json.JSONDecodeError, TypeError) as error:
        raise SeatSelectionError(
            "Invalid seat selection data. Please try again."
        ) from error
    if not isinstance(payload, dict):
        raise SeatSelectionError("Invalid seat selection data. Please try again.")
    requested = payload.get("seats")
    count = payload.get("passenger_count")
    if (
        not isinstance(requested, list)
        or type(count) is not int
        or not 1 <= count <= MAX_PASSENGERS
        or len(requested) != count
    ):
        raise SeatSelectionError(
            "Select between one and six seats, one for each passenger."
        )
    seats = []
    for item in requested:
        seat = seat_map.get(item.get("seat")) if isinstance(item, dict) else None
        if seat is None or item.get("class") != seat.cabin or seat in seats:
            raise SeatSelectionError("One or more selected seats are invalid.")
        seats.append(seat)
    if any(seat.code in occupied for seat in seats):
        raise SeatSelectionError(
            "Some selected seats are no longer available. "
            "Please select different seats."
        )
    return SeatSelection(flight_id=seat_map.flight.pk, seats=tuple(seats))


class SeatSelectionStore:
    session_key = "bookings_seat_selection"

    def __init__(self, session):
        self.session = session

    def save(self, selection):
        self.session[self.session_key] = {
            "flight": selection.flight_id,
            "seats": [seat.code for seat in selection.seats],
        }

    def load(self, seat_map):
        stored = self.session.get(self.session_key)
        if not isinstance(stored, dict) or stored.get("flight") != seat_map.flight.pk:
            return None
        codes = stored.get("seats")
        if not isinstance(codes, list) or not 1 <= len(codes) <= MAX_PASSENGERS:
            return None
        seats = tuple(seat_map.get(code) for code in codes)
        if None in seats or len(set(codes)) != len(codes):
            return None
        return SeatSelection(flight_id=seat_map.flight.pk, seats=seats)

    def clear(self):
        self.session.pop(self.session_key, None)
