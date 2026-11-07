import datetime

from django.db import models
from django.utils import timezone


def start_of_day(day):
    return timezone.make_aware(datetime.datetime.combine(day, datetime.time.min))


class ReferenceDataQuerySet(models.QuerySet):
    def unarchived(self):
        return self.filter(is_archived=False)

    def available(self):
        return self.unarchived().filter(is_active=True)


class FlightQuerySet(models.QuerySet):
    def unarchived(self):
        return self.filter(is_archived=False)

    def bookable(self):
        return self.unarchived().filter(departure__gt=timezone.now())

    def with_route(self):
        return self.select_related("airline", "from_airport", "to_airport", "aircraft")

    def on_route(self, origin, destination):
        return self.filter(from_airport=origin, to_airport=destination)

    def departing_on(self, day):
        return self.departing_between(day, day)

    def departing_between(self, first_day, last_day):
        return self.filter(
            departure__gte=start_of_day(first_day),
            departure__lt=start_of_day(last_day + datetime.timedelta(days=1)),
        )

    def domestic(self, country):
        return self.filter(from_airport__country=country, to_airport__country=country)
