from datetime import timedelta

from django.utils import timezone

BOARDING_WINDOW = timedelta(hours=2)


def schedule_progress(flight, now=None):
    now = now or timezone.now()
    if now < flight.departure - BOARDING_WINDOW:
        return "Scheduled", 0
    if now < flight.departure:
        return "Boarding", 0
    if now < flight.estimated_arrival:
        duration = max((flight.estimated_arrival - flight.departure).total_seconds(), 1)
        elapsed = (now - flight.departure).total_seconds()
        return "In flight", min(99, max(1, round(elapsed / duration * 100)))
    return "Landed", 100


def schedule_tracking_data(flight, now=None):
    now = now or timezone.now()
    status, progress = schedule_progress(flight, now)
    return {
        "id": flight.id,
        "code": flight.code,
        "airline": flight.airline.name,
        "from_code": flight.from_airport.code,
        "from_name": flight.from_airport.name,
        "to_code": flight.to_airport.code,
        "to_name": flight.to_airport.name,
        "departure": timezone.localtime(flight.departure).isoformat(),
        "arrival": timezone.localtime(flight.estimated_arrival).isoformat(),
        "status": status,
        "progress": progress,
        "updated_at": timezone.localtime(now).isoformat(),
    }
