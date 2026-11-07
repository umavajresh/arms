import datetime

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.flights.models import Flight, FlightSchedule
from apps.flights.querysets import start_of_day
from apps.flights.services.schedules import (
    ScheduleFlightGenerator,
    TemplateFlightCloner,
)


class Command(BaseCommand):
    help = "Generate dated flights from active recurring flight schedules."

    def add_arguments(self, parser):
        parser.add_argument(
            "--days", type=int, default=30, help="Number of days to generate."
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Delete future flights without reservations before generating.",
        )
        parser.add_argument(
            "--schedules",
            nargs="*",
            default=None,
            help="Limit generation to these schedule codes.",
        )

    def handle(self, *args, **options):
        today = timezone.localdate()
        end = today + datetime.timedelta(days=options["days"])
        self.stdout.write("Generating recurring flights from %s to %s" % (today, end))
        if options["clear"]:
            self.clear_future_flights(today)
        schedules = FlightSchedule.objects.filter(
            is_active=True, is_archived=False, end_date__gte=today
        )
        if options["schedules"]:
            schedules = schedules.filter(code__in=options["schedules"])
        if not schedules.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No flight schedules found; cloning existing flights instead."
                )
            )
            created = TemplateFlightCloner().clone(today, end)
            self.stdout.write(self.style.SUCCESS("Created %d flights." % created))
            return
        generator = ScheduleFlightGenerator()
        total = 0
        for schedule in schedules:
            created = generator.generate(schedule, today, end)
            self.stdout.write("  - %s: %d flights generated" % (schedule.code, created))
            total += created
        self.stdout.write(self.style.SUCCESS("Created %d new flights." % total))

    def clear_future_flights(self, today):
        future = Flight.objects.filter(
            departure__gte=start_of_day(today), reservations__isnull=True
        )
        deleted, _ = future.delete()
        self.stdout.write(self.style.WARNING("Deleted %d future flights" % deleted))
