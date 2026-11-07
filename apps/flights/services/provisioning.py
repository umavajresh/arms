import datetime
from dataclasses import dataclass
from decimal import Decimal

from django.utils import timezone

from apps.flights.models import Aircraft, Airline, Flight

from .window import BookingWindow

DOMESTIC_COUNTRY = "India"
PREFERRED_AIRCRAFT_CODES = ("A320", "B738", "A21N")
DEFAULT_BUSINESS_SLOTS = 12
DEFAULT_ECONOMY_SLOTS = 168
FLIGHT_DURATION = datetime.timedelta(hours=2, minutes=10)


@dataclass(frozen=True)
class DepartureSlot:
    departure_time: datetime.time
    sequence: int
    domestic_fares: tuple
    international_fares: tuple

    def fares_for(self, is_domestic):
        economy, business = (
            self.domestic_fares if is_domestic else self.international_fares
        )
        return Decimal(economy), Decimal(business)


DAILY_SLOTS = (
    DepartureSlot(datetime.time(8, 15), 1, ("3850", "11500"), ("24500", "58000")),
    DepartureSlot(datetime.time(14, 30), 2, ("4200", "12800"), ("26800", "64000")),
    DepartureSlot(datetime.time(19, 45), 3, ("4650", "14200"), ("28900", "72000")),
)


class RouteProvisioner:
    def __init__(self, slots=DAILY_SLOTS):
        self.slots = slots

    def ensure_departures(self, origin, destination, day):
        if origin.pk == destination.pk or day not in BookingWindow.current():
            return 0
        existing = Flight.objects.unarchived().on_route(origin, destination)
        if existing.departing_on(day).exists():
            return 0
        airline = self._default_airline()
        if airline is None:
            return 0
        aircraft = self._default_aircraft()
        is_domestic = origin.country == destination.country == DOMESTIC_COUNTRY
        created = 0
        for slot in self.slots:
            departure = timezone.make_aware(
                datetime.datetime.combine(day, slot.departure_time)
            )
            if departure <= timezone.now():
                continue
            economy_fare, business_fare = slot.fares_for(is_domestic)
            Flight.objects.create(
                code=self._flight_code(origin, destination, slot, day),
                airline=airline,
                from_airport=origin,
                to_airport=destination,
                aircraft=aircraft,
                departure=departure,
                estimated_arrival=departure + FLIGHT_DURATION,
                business_class_slots=DEFAULT_BUSINESS_SLOTS,
                economy_slots=DEFAULT_ECONOMY_SLOTS,
                business_class_price=business_fare,
                economy_price=economy_fare,
            )
            created += 1
        return created

    def _default_airline(self):
        return Airline.objects.available().first() or Airline.objects.first()

    def _default_aircraft(self):
        preferred = Aircraft.objects.available().filter(
            code__in=PREFERRED_AIRCRAFT_CODES
        )
        return preferred.first() or Aircraft.objects.first()

    def _flight_code(self, origin, destination, slot, day):
        code = "AR%s%s%d%02d" % (
            origin.code[:2],
            destination.code[:2],
            slot.sequence,
            day.day,
        )
        if Flight.objects.filter(code=code).exists():
            code = "%s-%s" % (code, day.strftime("%m%d"))
        return code
