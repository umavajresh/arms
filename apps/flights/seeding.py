import csv
import datetime
from decimal import Decimal
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from .models import Aircraft, Airline, Airport, Flight

SEED_DIRECTORY = Path(__file__).resolve().parent / "seed_data"


def _rows(path):
    with path.open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def _is_active(row):
    return row.get("status", "1") == "1"


def _next_year(moment):
    try:
        return moment.replace(year=moment.year + 1)
    except ValueError:
        return moment.replace(year=moment.year + 1, month=2, day=28)


def _future_window(departure, arrival):
    departure = datetime.datetime.fromisoformat(departure)
    arrival = datetime.datetime.fromisoformat(arrival)
    if timezone.is_naive(departure):
        departure = timezone.make_aware(departure)
    if timezone.is_naive(arrival):
        arrival = timezone.make_aware(arrival)
    while departure <= timezone.now():
        departure, arrival = _next_year(departure), _next_year(arrival)
    return departure, arrival


class ReferenceDataImporter:
    def __init__(self, directory=SEED_DIRECTORY):
        self.directory = directory

    @transaction.atomic
    def run(self):
        return {
            "airlines": self.import_airlines(),
            "airports": self.import_airports(),
            "aircraft": self.import_aircraft(),
            "flights": self.import_flights(),
        }

    def import_airlines(self):
        return sum(
            Airline.objects.update_or_create(
                code=row["code"],
                is_archived=False,
                defaults={
                    "name": row["name"],
                    "country": row["country"],
                    "is_active": _is_active(row),
                },
            )[1]
            for row in _rows(self.directory / "airlines.csv")
        )

    def import_airports(self):
        return sum(
            Airport.objects.update_or_create(
                code=row["code"],
                is_archived=False,
                defaults={
                    "name": row["name"],
                    "city": row["city"],
                    "country": row["country"],
                    "is_active": _is_active(row),
                },
            )[1]
            for row in _rows(self.directory / "airports.csv")
        )

    def import_aircraft(self):
        return sum(
            Aircraft.objects.update_or_create(
                code=row["code"],
                is_archived=False,
                defaults={
                    "model_name": row["model"],
                    "manufacturer": row["manufacturer"],
                    "business_capacity": int(row["business_capacity"]),
                    "economy_capacity": int(row["economy_capacity"]),
                },
            )[1]
            for row in _rows(self.directory / "aircraft.csv")
        )

    def import_flights(self):
        created = 0
        for row in _rows(self.directory / "flights.csv"):
            departure, arrival = _future_window(
                row["departure"], row["estimated_arrival"]
            )
            _, is_new = Flight.objects.update_or_create(
                code=row["code"],
                is_archived=False,
                defaults={
                    "airline": self._airline(row["airline_code"]),
                    "from_airport": self._airport(row["from_airport_code"]),
                    "to_airport": self._airport(row["to_airport_code"]),
                    "aircraft": self._aircraft(row["aircraft_code"]),
                    "departure": departure,
                    "estimated_arrival": arrival,
                    "business_class_price": Decimal(row["business_class_price"]),
                    "economy_price": Decimal(row["economy_price"]),
                },
            )
            created += is_new
        return created

    def _airline(self, code):
        return Airline.objects.get_or_create(
            code=code,
            is_archived=False,
            defaults={"name": code, "country": "Unknown"},
        )[0]

    def _airport(self, code):
        return Airport.objects.get_or_create(
            code=code,
            is_archived=False,
            defaults={"name": code, "city": "Unknown", "country": "Unknown"},
        )[0]

    def _aircraft(self, code):
        return Aircraft.objects.get_or_create(
            code=code,
            is_archived=False,
            defaults={"model_name": code, "manufacturer": "Unknown"},
        )[0]
