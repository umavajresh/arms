from django.core.management.base import BaseCommand
from django.db.models import Avg, Count, Max, Min

from apps.flights.models import Flight

DOMESTIC_COUNTRY = "India"


class Command(BaseCommand):
    help = "Display fare statistics for domestic flights."

    def handle(self, *args, **options):
        flights = Flight.objects.unarchived()
        domestic = flights.domestic(DOMESTIC_COUNTRY)
        total, domestic_total = flights.count(), domestic.count()
        share = domestic_total / total * 100 if total else 0
        self.stdout.write(self.style.SUCCESS("Flight Price Statistics"))
        self.stdout.write("Total flights: %d" % total)
        self.stdout.write("Domestic flights: %d (%.2f%%)" % (domestic_total, share))
        for label, field in (
            ("Economy", "economy_price"),
            ("Business", "business_class_price"),
        ):
            stats = domestic.aggregate(avg=Avg(field), low=Min(field), high=Max(field))
            self.stdout.write(
                "%s fares (INR): average %s, minimum %s, maximum %s"
                % (label, stats["avg"], stats["low"], stats["high"])
            )
        routes = (
            domestic.values("from_airport__name", "to_airport__name")
            .annotate(count=Count("id"))
            .order_by("-count")[:5]
        )
        self.stdout.write("Top domestic routes:")
        for rank, route in enumerate(routes, 1):
            self.stdout.write(
                "  %d. %s to %s - %d flights"
                % (
                    rank,
                    route["from_airport__name"],
                    route["to_airport__name"],
                    route["count"],
                )
            )
