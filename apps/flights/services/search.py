from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from django.db.models import Max, Min, Q

from apps.flights.models import Flight

DEPARTURE_WINDOWS = {
    "morning": Q(departure__hour__gte=6, departure__hour__lt=12),
    "afternoon": Q(departure__hour__gte=12, departure__hour__lt=17),
    "evening": Q(departure__hour__gte=17, departure__hour__lt=21),
    "night": Q(departure__hour__gte=21) | Q(departure__hour__lt=6),
}

PRICE_ORDERINGS = {"asc": "economy_price", "desc": "-economy_price"}


def parse_price(value):
    try:
        price = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return price if price.is_finite() and price >= 0 else None


@dataclass
class SearchFilters:
    price_sort: str = ""
    min_price: str = ""
    max_price: str = ""
    time_filter: str = ""

    @classmethod
    def from_query(cls, query):
        return cls(
            price_sort=query.get("price_sort", ""),
            min_price=query.get("min_price", ""),
            max_price=query.get("max_price", ""),
            time_filter=query.get("time_filter", ""),
        )

    @property
    def is_filtering(self):
        return bool(self.time_filter or self.min_price or self.max_price)

    def apply(self, flights):
        minimum = parse_price(self.min_price)
        maximum = parse_price(self.max_price)
        if minimum is not None:
            flights = flights.filter(
                Q(economy_price__gte=minimum) | Q(business_class_price__gte=minimum)
            )
        if maximum is not None:
            flights = flights.filter(
                Q(economy_price__lte=maximum) | Q(business_class_price__lte=maximum)
            )
        window = DEPARTURE_WINDOWS.get(self.time_filter)
        if window is not None:
            flights = flights.filter(window)
        return flights.order_by(PRICE_ORDERINGS.get(self.price_sort, "departure"))


@dataclass
class SearchOutcome:
    flights: object
    nearby_flights: list = field(default_factory=list)
    filter_relaxed: bool = False
    unfiltered_count: int = 0
    min_available_price: object = 0
    max_available_price: object = 1000


class FlightSearch:
    nearby_limit = 6

    def __init__(self, origin, destination, day, prepare=None):
        self.origin = origin
        self.destination = destination
        self.day = day
        self.prepare = prepare or (lambda flights: flights)

    def route_queryset(self):
        flights = Flight.objects.bookable().with_route()
        return self.prepare(flights.on_route(self.origin, self.destination))

    def base_queryset(self):
        return self.route_queryset().departing_on(self.day)

    def run(self, filters):
        base = self.base_queryset()
        filtered = filters.apply(base)
        if filtered.exists():
            return self._outcome(filtered, base)
        if filters.is_filtering and base.exists():
            outcome = self._outcome(base.order_by("departure"), base)
            outcome.filter_relaxed = True
            outcome.unfiltered_count = base.count()
            return outcome
        nearby = list(self.route_queryset().order_by("departure")[: self.nearby_limit])
        return SearchOutcome(flights=Flight.objects.none(), nearby_flights=nearby)

    def _outcome(self, flights, base):
        prices = base.aggregate(
            low=Min("economy_price"), high=Max("business_class_price")
        )
        return SearchOutcome(
            flights=flights,
            min_available_price=prices["low"] or 0,
            max_available_price=prices["high"] or 1000,
        )
