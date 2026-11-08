import datetime

from django.utils import timezone

from apps.flights.models import Flight


def _daterange(start, end):
    day = start
    while day <= end:
        yield day
        day += datetime.timedelta(days=1)


class ScheduleFlightGenerator:
    def generate(self, schedule, start, end):
        end = min(end, schedule.end_date)
        return sum(
            self._create_flight(schedule, day)
            for day in _daterange(start, end)
            if schedule.operates_on(day)
        )

    def generate_upcoming(self, schedule, days_ahead=30):
        today = timezone.localdate()
        return self.generate(
            schedule, today, today + datetime.timedelta(days=days_ahead)
        )

    def _create_flight(self, schedule, day):
        departure = datetime.datetime.combine(
            day, schedule.departure_time, tzinfo=timezone.get_current_timezone()
        )
        code = "%s-%s" % (schedule.code, day.strftime("%m%d"))
        _, created = Flight.objects.get_or_create(
            code=code,
            airline=schedule.airline,
            from_airport=schedule.from_airport,
            to_airport=schedule.to_airport,
            departure=departure,
            defaults={
                "aircraft": schedule.aircraft,
                "estimated_arrival": departure
                + datetime.timedelta(minutes=schedule.duration_minutes),
                "business_class_price": schedule.business_class_price,
                "economy_price": schedule.economy_price,
                "currency": schedule.currency,
            },
        )
        return int(created)
