import datetime

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.bookings.selectors import with_seat_availability
from apps.flights.models import Flight


class Command(BaseCommand):
    help = "List upcoming flights with remaining seat counts."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=7, help="Days to include.")
        parser.add_argument("--airline", help="Filter by airline code.")
        parser.add_argument("--airport", help="Filter by origin or destination code.")

    def handle(self, *args, **options):
        today = timezone.localdate()
        end = today + datetime.timedelta(days=options["days"])
        flights = Flight.objects.unarchived().with_route()
        flights = flights.filter(departure__date__gte=today, departure__date__lte=end)
        if options["airline"]:
            flights = flights.filter(airline__code__iexact=options["airline"])
        if options["airport"]:
            flights = flights.filter(
                Q(from_airport__code__iexact=options["airport"])
                | Q(to_airport__code__iexact=options["airport"])
            )
        flights = with_seat_availability(flights.order_by("departure"))
        self.stdout.write(
            self.style.SUCCESS("Upcoming Flights (%s to %s):" % (today, end))
        )
        for flight in flights:
            self.stdout.write(
                "%s | %s | %s -> %s | %s | Economy: %s | Business: %s"
                % (
                    flight.code,
                    flight.airline.name,
                    flight.from_airport.code,
                    flight.to_airport.code,
                    timezone.localtime(flight.departure).strftime("%Y-%m-%d %H:%M"),
                    flight.available_economy,
                    flight.available_business,
                )
            )
        self.stdout.write(self.style.SUCCESS("Total: %d flights found" % len(flights)))
