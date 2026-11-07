from datetime import timedelta

from django.utils import timezone

from apps.flights.models import Aircraft, Airline, Airport, Flight


def make_airline(code="TSA", name="Test Air", **fields):
    return Airline.objects.create(code=code, name=name, **fields)


def make_airport(code, name=None, city="", country="India", **fields):
    return Airport.objects.create(
        code=code,
        name=name or "%s Airport" % code,
        city=city,
        country=country,
        **fields,
    )


def make_aircraft(code="AC01", business_capacity=4, economy_capacity=10, **fields):
    fields.setdefault("model_name", "Airbus A320")
    fields.setdefault("manufacturer", "Airbus")
    return Aircraft.objects.create(
        code=code,
        business_capacity=business_capacity,
        economy_capacity=economy_capacity,
        **fields,
    )


def make_flight(
    code="TS100",
    airline=None,
    origin=None,
    destination=None,
    departs_in=timedelta(days=7),
    duration=timedelta(hours=2),
    **fields,
):
    departure = timezone.now() + departs_in
    fields.setdefault("business_class_slots", 5)
    fields.setdefault("economy_slots", 11)
    fields.setdefault("business_class_price", 12000)
    fields.setdefault("economy_price", 5000)
    return Flight.objects.create(
        code=code,
        airline=airline or make_airline(),
        from_airport=origin or make_airport("ORG"),
        to_airport=destination or make_airport("DST"),
        departure=departure,
        estimated_arrival=departure + duration,
        **fields,
    )
