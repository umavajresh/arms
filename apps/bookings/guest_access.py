import re

from django.utils.crypto import constant_time_compare

from .models import Reservation

GUEST_REFERENCE_PATTERN = re.compile(r"GUEST-[A-Z0-9]{4}-[A-Z0-9]{4}")
MAX_VERIFIER_LENGTH = 254


def normalize_reference(reference):
    return (reference or "").strip().upper()


def normalize_verifier(verifier):
    return (verifier or "").strip().casefold()


def is_valid_guest_request(reference, verifier):
    return bool(
        GUEST_REFERENCE_PATTERN.fullmatch(reference)
        and verifier
        and len(verifier) <= MAX_VERIFIER_LENGTH
    )


def passenger_matches(reservation, verifier):
    return constant_time_compare(
        reservation.email.casefold(), verifier
    ) or constant_time_compare(reservation.last_name.casefold(), verifier)


def find_guest_booking(reference, verifier):
    booking = list(
        Reservation.objects.with_flight()
        .filter(booking_reference=reference, is_guest=True)
        .order_by("pk")
    )
    if any(passenger_matches(reservation, verifier) for reservation in booking):
        return booking
    return []


class GuestAccess:
    granted_key = "bookings_verified_guest_reference"
    created_key = "bookings_last_guest_reference"

    def __init__(self, session):
        self.session = session

    def grant(self, reference):
        self.session[self.granted_key] = reference

    def remember_new_booking(self, reference):
        self.session[self.created_key] = reference

    def allows(self, reference):
        return reference in {
            self.session.get(self.granted_key),
            self.session.get(self.created_key),
        }
