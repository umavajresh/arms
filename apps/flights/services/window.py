import datetime
from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone


@dataclass(frozen=True)
class BookingWindow:
    earliest: datetime.date
    latest: datetime.date

    @classmethod
    def current(cls):
        today = timezone.localdate()
        horizon = datetime.timedelta(days=settings.ARMS_BOOKING_HORIZON_DAYS)
        return cls(earliest=today, latest=today + horizon)

    def __contains__(self, day):
        return self.earliest <= day <= self.latest
