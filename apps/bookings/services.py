from dataclasses import dataclass

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.flights.models import Flight
from apps.notifications.models import Notification
from apps.notifications.services import notify

from .models import Reservation
from .seating import SeatMap


class ReservationRejected(Exception):
    def __init__(self, message, http_status=400):
        super().__init__(message)
        self.message = message
        self.http_status = http_status


@dataclass(frozen=True)
class PassengerDetails:
    first_name: str
    middle_name: str
    last_name: str
    gender: str


@dataclass(frozen=True)
class ContactDetails:
    email: str
    contact: str
    address: str


class ReservationService:
    def submit(self, selection, passengers, contact, user=None):
        try:
            with transaction.atomic():
                flight = self._lock_flight(selection.flight_id)
                self._ensure_seats_still_valid(flight, selection)
                return [
                    Reservation.objects.create(
                        flight=flight,
                        user=user,
                        cabin=seat.cabin,
                        seat_number=seat.code,
                        first_name=passenger.first_name,
                        middle_name=passenger.middle_name,
                        last_name=passenger.last_name,
                        gender=passenger.gender,
                        email=contact.email,
                        contact=contact.contact,
                        address=contact.address,
                    )
                    for seat, passenger in zip(selection.seats, passengers)
                ]
        except IntegrityError as error:
            raise ReservationRejected(
                "A selected seat is no longer available. Please choose another seat.",
                http_status=409,
            ) from error

    def cancel(self, reservation):
        if not reservation.can_cancel:
            raise ReservationRejected(reservation.cancellation_status, http_status=409)
        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status", "updated_at"])

    def _lock_flight(self, flight_id):
        flight = Flight.objects.select_for_update().filter(pk=flight_id).first()
        if flight is None or flight.is_archived:
            raise ReservationRejected("The selected flight is unavailable.")
        if flight.departure <= timezone.now():
            raise ReservationRejected("This flight has already departed.")
        return flight

    def _ensure_seats_still_valid(self, flight, selection):
        seat_map = SeatMap(flight)
        if any(seat_map.get(seat.code) != seat for seat in selection.seats):
            raise ReservationRejected(
                "The selected seats are no longer valid.", http_status=409
            )
        if Reservation.objects.occupied_seat_numbers(flight) & selection.seat_codes:
            raise ReservationRejected(
                "A selected seat is no longer available. Please choose another seat.",
                http_status=409,
            )


class ReservationDecisionService:
    def approve(self, reservation):
        if not reservation.can_be_approved:
            return False
        self._set_status(reservation, Reservation.Status.APPROVED)
        self._notify(
            reservation,
            Notification.Kind.RESERVATION_APPROVED,
            "Reservation Approved - Flight %s" % reservation.flight.code,
            self._approval_message(reservation),
        )
        return True

    def reject(self, reservation):
        if reservation.status != Reservation.Status.PENDING:
            return False
        self._set_status(reservation, Reservation.Status.REJECTED)
        self._notify(
            reservation,
            Notification.Kind.RESERVATION_REJECTED,
            "Reservation Rejected - Flight %s" % reservation.flight.code,
            self._rejection_message(reservation),
        )
        return True

    def cancel(self, reservation):
        if not reservation.is_active:
            return False
        self._set_status(reservation, Reservation.Status.CANCELLED)
        return True

    def _set_status(self, reservation, status):
        reservation.status = status
        reservation.save(update_fields=["status", "updated_at"])

    def _notify(self, reservation, kind, title, message):
        if reservation.user_id:
            notify(reservation.user, kind, title, message)

    def _route(self, reservation):
        flight = reservation.flight
        return "%s to %s" % (flight.from_airport.name, flight.to_airport.name)

    def _departure(self, reservation):
        departure = timezone.localtime(reservation.flight.departure)
        return departure.strftime("%B %d, %Y at %I:%M %p")

    def _approval_message(self, reservation):
        return "\n".join(
            [
                "Great news! Your reservation for Flight %s has been approved."
                % reservation.flight.code,
                "",
                "Flight Details:",
                "- Route: %s" % self._route(reservation),
                "- Departure: %s" % self._departure(reservation),
                "- Seat: %s" % reservation.seat_number,
                "- Class: %s" % reservation.get_cabin_display(),
                "",
                "Your booking is now confirmed. Please arrive at the airport "
                "at least 2 hours before departure.",
            ]
        )

    def _rejection_message(self, reservation):
        return "\n".join(
            [
                "We regret to inform you that your reservation for Flight %s "
                "has been rejected." % reservation.flight.code,
                "",
                "Flight Details:",
                "- Route: %s" % self._route(reservation),
                "- Departure: %s" % self._departure(reservation),
                "",
                "Please contact our customer service for more details "
                "or try booking another flight.",
            ]
        )
