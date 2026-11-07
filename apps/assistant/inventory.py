import datetime

from django.db.models import Q
from django.utils import timezone

from apps.bookings.selectors import with_seat_availability
from apps.flights.models import Flight

DOMESTIC_COUNTRY = "India"
DOMESTIC_HUB_CODES = ("MAA", "BLR", "HYD", "DEL", "BOM")
DESTINATION_ALIASES = {"bali": ("Bali", "Denpasar", "DPS")}
DISPLAY_FORMAT = "%d %b %Y, %I:%M %p"


def format_moment(moment):
    return timezone.localtime(moment).strftime(DISPLAY_FORMAT)


def recorded_flights():
    return with_seat_availability(Flight.objects.unarchived().with_route())


def bookable_flights():
    return with_seat_availability(Flight.objects.bookable().with_route())


def airport_matches(prefix, term):
    return (
        Q(**{"%s__name__icontains" % prefix: term})
        | Q(**{"%s__code__icontains" % prefix: term})
        | Q(**{"%s__city__icontains" % prefix: term})
    )


def flight_summary(flight):
    return {
        "id": flight.id,
        "code": flight.code,
        "airline": flight.airline.name,
        "from": "%s - %s" % (flight.from_airport.code, flight.from_airport.name),
        "to": "%s - %s" % (flight.to_airport.code, flight.to_airport.name),
        "departure": format_moment(flight.departure),
        "arrival": format_moment(flight.estimated_arrival),
        "economy_price": float(flight.economy_price),
        "business_price": float(flight.business_class_price),
        "currency": flight.currency,
        "economy_available": flight.available_economy,
        "business_available": flight.available_business,
    }


def _narrow(queryset, condition):
    narrowed = queryset.filter(condition)
    return narrowed if narrowed.exists() else queryset


def _month_window(month):
    today = timezone.localdate()
    if month in ("this month", "next month"):
        start = today.replace(day=1)
        if month == "next month":
            start = (start + datetime.timedelta(days=32)).replace(day=1)
        end = (start + datetime.timedelta(days=32)).replace(day=1)
        return Q(departure__date__gte=start, departure__date__lt=end)
    try:
        number = datetime.datetime.strptime(month, "%B").month
    except ValueError:
        return None
    year = today.year + (number < today.month)
    return Q(departure__year=year, departure__month=number)


def search_real_flights(preferences, limit=5):
    queryset = bookable_flights()
    trip_type = preferences.get("trip_type", "domestic")
    if trip_type == "domestic":
        queryset = queryset.domestic(DOMESTIC_COUNTRY)
    elif trip_type == "international":
        queryset = queryset.exclude(to_airport__country__iexact=DOMESTIC_COUNTRY)
        queryset = queryset.exclude(to_airport__country="")
    origin = (preferences.get("origin") or "").strip()
    if origin:
        queryset = _narrow(queryset, airport_matches("from_airport", origin))
    destination = (preferences.get("destination") or "").strip()
    if destination:
        condition = Q()
        for alias in DESTINATION_ALIASES.get(destination.lower(), (destination,)):
            condition |= airport_matches("to_airport", alias)
        matches = queryset.filter(condition)
        if matches.exists():
            queryset = matches
        elif trip_type == "domestic":
            queryset = _narrow(queryset, Q(to_airport__code__in=DOMESTIC_HUB_CODES))
    month = preferences.get("month")
    window = _month_window(month) if month else None
    if window is not None:
        queryset = queryset.filter(window)
    budget = preferences.get("budget")
    if budget:
        queryset = _narrow(queryset, Q(economy_price__lte=budget))
    return [
        flight_summary(flight) for flight in queryset.order_by("economy_price")[:limit]
    ]
