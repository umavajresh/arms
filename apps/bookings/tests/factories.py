from apps.bookings.models import Reservation


def make_reservation(flight, user=None, seat_number="E1A", **fields):
    fields.setdefault("cabin", Reservation.Cabin.ECONOMY)
    fields.setdefault("first_name", "Test")
    fields.setdefault("last_name", "Passenger")
    fields.setdefault("gender", Reservation.Gender.FEMALE)
    fields.setdefault("email", "test.passenger@example.com")
    fields.setdefault("contact", "5550102")
    return Reservation.objects.create(
        flight=flight, user=user, seat_number=seat_number, **fields
    )
