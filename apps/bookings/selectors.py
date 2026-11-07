from django.db.models import Count, F, Q

from .models import Reservation


def _active_reservations_in(cabin):
    return Count(
        "reservations",
        filter=Q(
            reservations__status__in=Reservation.ACTIVE_STATUSES,
            reservations__cabin=cabin,
        ),
    )


def with_seat_availability(flights):
    return flights.annotate(
        booked_business=_active_reservations_in(Reservation.Cabin.BUSINESS),
        booked_economy=_active_reservations_in(Reservation.Cabin.ECONOMY),
        reservation_count=Count("reservations", distinct=True),
    ).annotate(
        available_business=F("business_class_slots") - F("booked_business"),
        available_economy=F("economy_slots") - F("booked_economy"),
    )


def occupancy_percent(booked, capacity):
    return float(booked) / capacity * 100 if capacity else 0.0
