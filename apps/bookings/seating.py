from dataclasses import dataclass

from .models import Reservation

CABIN_LAYOUTS = {
    Reservation.Cabin.BUSINESS: ("B", "ABCD"),
    Reservation.Cabin.ECONOMY: ("E", "ABCDEF"),
}


@dataclass(frozen=True)
class Seat:
    code: str
    cabin: str

    @property
    def cabin_label(self):
        return Reservation.Cabin(self.cabin).label


class SeatMap:
    def __init__(self, flight):
        self.flight = flight
        capacities = {
            Reservation.Cabin.BUSINESS: flight.business_class_slots,
            Reservation.Cabin.ECONOMY: flight.economy_slots,
        }
        self.seats = {
            seat.code: seat
            for cabin, capacity in capacities.items()
            for seat in self._layout(cabin, capacity)
        }

    def _layout(self, cabin, capacity):
        prefix, letters = CABIN_LAYOUTS[cabin]
        for index in range(capacity):
            row, column = divmod(index, len(letters))
            yield Seat("%s%d%s" % (prefix, row + 1, letters[column]), cabin)

    def get(self, code):
        return self.seats.get(code) if isinstance(code, str) else None

    def availability(self, cabin, occupied):
        return [
            {"seat": seat.code, "available": seat.code not in occupied}
            for seat in self.seats.values()
            if seat.cabin == cabin
        ]

    def fare_for(self, seat):
        if seat.cabin == Reservation.Cabin.BUSINESS:
            return self.flight.business_class_price
        return self.flight.economy_price
