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


class TemplateFlightCloner:
    def clone(self, start, end):
        created = 0
        for template in Flight.objects.unarchived().select_related("aircraft"):
            duration = template.estimated_arrival - template.departure
            departure_time = timezone.localtime(template.departure).timetz()
            for day in _daterange(start, end):
                departure = datetime.datetime.combine(day, departure_time)
                code = "%s-%s" % (template.code, day.strftime("%m%d"))
                if Flight.objects.filter(code=code, departure__date=day).exists():
                    continue
                Flight.objects.create(
                    code=code,
                    airline=template.airline,
                    from_airport=template.from_airport,
                    to_airport=template.to_airport,
                    aircraft=template.aircraft,
                    departure=departure,
                    estimated_arrival=departure + duration,
                    business_class_price=template.business_class_price,
                    economy_price=template.economy_price,
                    currency=template.currency,
                )
                created += 1
        return created
