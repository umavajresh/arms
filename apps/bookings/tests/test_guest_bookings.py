import json

from django.core.cache import cache
from django.test import TestCase
from django.urls import reverse

from apps.bookings.models import Reservation
from apps.flights.tests.factories import make_aircraft, make_flight

from .factories import make_reservation


class GuestBookingTests(TestCase):
    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        self.flight = make_flight(code="GL100", aircraft=make_aircraft())

    def guest_reservation(self, **fields):
        fields.setdefault("first_name", "Alex")
        fields.setdefault("last_name", "Morgan")
        fields.setdefault("email", "alex.morgan@example.com")
        return make_reservation(self.flight, seat_number="E1B", **fields)

    def lookup(self, reference, verification):
        return self.client.post(
            reverse("bookings:guest-lookup"),
            {"reference": reference, "verification": verification},
        )

    def submit_group(self, travellers):
        seats = [
            {"seat": "E1%s" % letter, "class": "economy"}
            for letter in "ABCDEF"[: len(travellers)]
        ]
        self.client.post(
            reverse("bookings:seat-selection", args=[self.flight.pk]),
            {
                "selected_seats": json.dumps(
                    {"passenger_count": len(travellers), "seats": seats}
                )
            },
        )
        data = {
            "flight": str(self.flight.pk),
            "passenger_count": str(len(travellers)),
            "email": "family@example.com",
            "contact": "555-1234",
            "is_guest": "1",
        }
        for index, ((first, last), seat) in enumerate(zip(travellers, seats)):
            data.update(
                {
                    "passenger_%d-first_name" % index: first,
                    "passenger_%d-last_name" % index: last,
                    "passenger_%d-gender" % index: "Female",
                    "passenger_%d_seat" % index: seat["seat"],
                    "passenger_%d_class" % index: "economy",
                }
            )
        return self.client.post(reverse("bookings:submit"), data).json()

    def test_group_booking_shares_one_reference(self):
        data = self.submit_group([("Priya", "Raman"), ("Kiran", "Rao")])
        booking = Reservation.objects.filter(
            booking_reference=data["booking_reference"]
        )
        self.assertEqual(booking.count(), 2)
        confirmation = self.client.get(data["redirect"])
        self.assertContains(confirmation, "Priya")
        self.assertContains(confirmation, "Kiran")

    def test_lookup_by_any_traveller_lists_the_whole_booking(self):
        data = self.submit_group([("Priya", "Raman"), ("Kiran", "Rao")])
        response = self.lookup(data["booking_reference"], "Rao")
        self.assertEqual(len(response.context["booking_passengers"]), 2)
        self.assertContains(response, "2 travellers on this booking")

    def test_guest_cancel_cancels_every_traveller(self):
        data = self.submit_group([("Priya", "Raman"), ("Kiran", "Rao")])
        response = self.client.post(
            reverse("bookings:guest-cancel"),
            {"reference": data["booking_reference"], "verification": "raman"},
        )
        self.assertEqual(response.json()["status"], "success")
        self.assertIn("2 travellers", response.json()["msg"])
        statuses = set(
            Reservation.objects.filter(
                booking_reference=data["booking_reference"]
            ).values_list("status", flat=True)
        )
        self.assertEqual(statuses, {Reservation.Status.CANCELLED})

    def test_guest_can_book_and_view_confirmation(self):
        self.client.post(
            reverse("bookings:seat-selection", args=[self.flight.pk]),
            {
                "selected_seats": json.dumps(
                    {
                        "passenger_count": 1,
                        "seats": [{"seat": "E1A", "class": "economy"}],
                    }
                )
            },
        )
        response = self.client.post(
            reverse("bookings:submit"),
            {
                "flight": str(self.flight.pk),
                "passenger_count": "1",
                "passenger_0-first_name": "Jane",
                "passenger_0-last_name": "Doe",
                "passenger_0-gender": "Female",
                "passenger_0_seat": "E1A",
                "passenger_0_class": "economy",
                "email": "jane.doe@example.com",
                "contact": "555-1234",
                "is_guest": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIs(data["is_guest"], True)
        self.assertTrue(data["booking_reference"].startswith("GUEST-"))
        reservation = Reservation.objects.get(
            booking_reference=data["booking_reference"]
        )
        self.assertIsNone(reservation.user)
        self.assertIs(reservation.is_guest, True)
        confirmation = self.client.get(data["redirect"])
        self.assertContains(confirmation, data["booking_reference"])
        self.assertContains(confirmation, "Jane")

    def test_guest_lookup_accepts_email_or_last_name(self):
        reservation = self.guest_reservation()
        for verification in ("alex.morgan@example.com", "Morgan"):
            with self.subTest(verification=verification):
                response = self.lookup(reservation.booking_reference, verification)
                self.assertContains(response, "Alex")
                self.assertContains(response, reservation.booking_reference)

    def test_guest_lookup_rejects_wrong_passenger(self):
        reservation = self.guest_reservation()
        response = self.lookup(reservation.booking_reference, "wrong@example.com")
        self.assertContains(response, "No booking matches that reference")

    def test_confirmation_requires_verified_session(self):
        reservation = self.guest_reservation(first_name="Taylor", last_name="Guest")
        url = reverse("bookings:confirmation", args=[reservation.booking_reference])
        self.assertRedirects(self.client.get(url), reverse("bookings:guest-lookup"))
        self.lookup(reservation.booking_reference, reservation.email)
        self.assertContains(self.client.get(url), "Taylor")

    def test_guest_cancellation_attempts_are_rate_limited_by_ip(self):
        responses = [
            self.client.post(reverse("bookings:guest-cancel"), {}) for _ in range(6)
        ]
        self.assertEqual([r.status_code for r in responses[:5]], [400] * 5)
        self.assertEqual(responses[5].status_code, 429)

    def test_guest_can_cancel_with_matching_details(self):
        reservation = self.guest_reservation(email="robert@example.com")
        denied = self.client.post(
            reverse("bookings:guest-cancel"),
            {
                "reference": reservation.booking_reference,
                "verification": "x@example.com",
            },
        )
        self.assertEqual(denied.status_code, 403)
        allowed = self.client.post(
            reverse("bookings:guest-cancel"),
            {
                "reference": reservation.booking_reference,
                "verification": "robert@example.com",
            },
        )
        self.assertEqual(allowed.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)
