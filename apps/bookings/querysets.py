from django.db import models


class ReservationQuerySet(models.QuerySet):
    def active(self):
        return self.filter(status__in=self.model.ACTIVE_STATUSES)

    def with_flight(self):
        return self.select_related(
            "flight",
            "flight__airline",
            "flight__aircraft",
            "flight__from_airport",
            "flight__to_airport",
        )

    def occupied_seat_numbers(self, flight):
        return set(
            self.active().filter(flight=flight).values_list("seat_number", flat=True)
        )
