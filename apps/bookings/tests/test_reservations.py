import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import (
    DEFAULT_PASSWORD,
    make_administrator,
    make_user,
)
from apps.bookings.models import Reservation
from apps.flights.tests.factories import make_airport, make_flight

from .factories import make_reservation


class ReservationFlowMixin:
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user(username="reservation-test-user")
        cls.admin = make_administrator(username="reservation-test-admin")
        cls.flight = make_flight(
            code="RTEST1",
            origin=make_airport("TST", city="Origin"),
            destination=make_airport("DST", city="Destination"),
            departs_in=timedelta(days=14),
        )

    def select_seats(self, *seats):
        payload = {
            "passenger_count": len(seats),
            "seats": [{"seat": seat, "class": cabin} for seat, cabin in seats],
        }
        return self.client.post(
            reverse("bookings:seat-selection", args=[self.flight.pk]),
            {"selected_seats": json.dumps(payload)},
        )

    def verify(self, password=DEFAULT_PASSWORD, answer=None):
        self.client.get(reverse("bookings:human-check"))
        expected = self.client.session["bookings_check_answer"]
        return self.client.post(
            reverse("bookings:verify"),
            {"password": password, "check_answer": answer or expected},
        )

    def submission(self, **overrides):
        data = {
            "flight": str(self.flight.pk),
            "passenger_count": "1",
            "passenger_0-first_name": "Test",
            "passenger_0-middle_name": "",
            "passenger_0-last_name": "Passenger",
            "passenger_0-gender": "Female",
            "passenger_0_seat": "E1A",
            "passenger_0_class": "economy",
            "email": "test.passenger@example.com",
            "contact": "5550102",
            "address": "",
        }
        data.update(overrides)
        return data

    def submit(self, **overrides):
        return self.client.post(
            reverse("bookings:submit"), self.submission(**overrides)
        )


class SeatSelectionTests(ReservationFlowMixin, TestCase):
    def test_seat_map_matches_configured_capacity_and_cabin_codes(self):
        response = self.client.get(
            reverse("bookings:seat-selection", args=[self.flight.pk])
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [seat["seat"] for seat in response.context["business_seats"]],
            ["B1A", "B1B", "B1C", "B1D", "B2A"],
        )
        self.assertEqual(
            [seat["seat"] for seat in response.context["economy_seats"]],
            [
                "E1A",
                "E1B",
                "E1C",
                "E1D",
                "E1E",
                "E1F",
                "E2A",
                "E2B",
                "E2C",
                "E2D",
                "E2E",
            ],
        )

    def test_seat_map_marks_active_reservations_unavailable(self):
        make_reservation(self.flight, user=self.user, seat_number="E1B")
        make_reservation(
            self.flight,
            seat_number="E1C",
            status=Reservation.Status.CANCELLED,
        )
        response = self.client.get(
            reverse("bookings:seat-selection", args=[self.flight.pk])
        )
        availability = {
            seat["seat"]: seat["available"]
            for seat in response.context["economy_seats"]
        }
        self.assertIs(availability["E1B"], False)
        self.assertIs(availability["E1C"], True)

    def test_fabricated_seat_codes_are_rejected(self):
        response = self.select_seats(("E999Z", "economy"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("bookings_seat_selection", self.client.session)

    def test_cabin_mismatch_is_rejected(self):
        self.select_seats(("E1A", "business"))
        self.assertNotIn("bookings_seat_selection", self.client.session)

    def test_valid_selection_continues_to_passenger_details(self):
        response = self.select_seats(("E1A", "economy"), ("B1A", "business"))
        self.assertRedirects(
            response, reverse("bookings:reservation-form", args=[self.flight.pk])
        )

    def test_departed_flight_cannot_be_selected(self):
        departed = make_flight(
            code="PAST1",
            airline=self.flight.airline,
            origin=self.flight.from_airport,
            destination=self.flight.to_airport,
            departs_in=-timedelta(hours=1),
        )
        response = self.client.get(
            reverse("bookings:seat-selection", args=[departed.pk])
        )
        self.assertRedirects(response, reverse("flights:search"))

    def test_administrators_are_sent_to_console(self):
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("bookings:seat-selection", args=[self.flight.pk])
        )
        self.assertRedirects(response, reverse("console:dashboard"))


class ReservationFormTests(ReservationFlowMixin, TestCase):
    def test_form_requires_a_seat_selection(self):
        response = self.client.get(
            reverse("bookings:reservation-form", args=[self.flight.pk])
        )
        self.assertRedirects(
            response, reverse("bookings:seat-selection", args=[self.flight.pk])
        )

    def test_form_uses_a_json_script_for_server_selected_seats(self):
        self.client.force_login(self.user)
        self.select_seats(("E1A", "economy"))
        response = self.client.get(
            reverse("bookings:reservation-form", args=[self.flight.pk])
        )
        self.assertContains(response, 'id="reservation-payload"')
        self.assertContains(response, '"seat": "E1A"')
        self.assertEqual(response.context["total_price"], 5000.0)


class ReservationSubmissionTests(ReservationFlowMixin, TestCase):
    def test_anonymous_submission_requires_guest_flag(self):
        self.select_seats(("E1A", "economy"))
        self.assertEqual(self.submit().status_code, 401)
        self.assertIs(Reservation.objects.exists(), False)

    def test_signed_in_submission_requires_verification(self):
        self.client.force_login(self.user)
        self.select_seats(("E1A", "economy"))
        self.assertEqual(self.submit().status_code, 403)
        self.assertIs(Reservation.objects.exists(), False)

    def test_verified_booking_saves_the_server_selected_seat(self):
        self.client.force_login(self.user)
        self.select_seats(("E1A", "economy"))
        self.assertEqual(self.verify().status_code, 200)
        tampered = self.submit(passenger_0_seat="B1A", passenger_0_class="business")
        self.assertEqual(tampered.status_code, 400)
        response = self.submit()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["redirect"], reverse("bookings:my-reservations")
        )
        reservation = Reservation.objects.get()
        self.assertEqual(reservation.seat_number, "E1A")
        self.assertEqual(reservation.cabin, Reservation.Cabin.ECONOMY)
        self.assertEqual(reservation.user, self.user)
        self.assertEqual(reservation.status, Reservation.Status.PENDING)
        self.assertTrue(reservation.booking_reference.startswith("ARMS-"))
        self.assertNotIn("bookings_verified_until", self.client.session)

    def test_group_booking_creates_one_reservation_per_passenger(self):
        self.client.force_login(self.user)
        self.select_seats(("E1A", "economy"), ("B1A", "business"))
        self.verify()
        response = self.submit(
            passenger_count="2",
            **{
                "passenger_1-first_name": "Second",
                "passenger_1-last_name": "Traveller",
                "passenger_1-gender": "Male",
                "passenger_1_seat": "B1A",
                "passenger_1_class": "business",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            sorted(Reservation.objects.values_list("seat_number", flat=True)),
            ["B1A", "E1A"],
        )

    def test_invalid_passenger_details_are_rejected(self):
        self.client.force_login(self.user)
        self.select_seats(("E1A", "economy"))
        self.verify()
        response = self.submit(**{"passenger_0-gender": "Unknown"})
        self.assertEqual(response.status_code, 400)
        self.assertIn("Passenger 1", response.json()["msg"])

    def test_cannot_double_book_an_occupied_seat(self):
        self.client.force_login(self.user)
        self.select_seats(("E1A", "economy"))
        self.verify()
        make_reservation(
            self.flight, seat_number="E1A", status=Reservation.Status.APPROVED
        )
        response = self.submit()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Reservation.objects.count(), 1)

    def test_verification_locks_after_five_failures(self):
        self.client.force_login(self.user)
        for _ in range(5):
            response = self.verify(password="incorrect-password")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["status"], "failed")

    def test_wrong_human_check_answer_fails_verification(self):
        self.client.force_login(self.user)
        response = self.verify(answer="999")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["msg"], "Incorrect answer. Please try again.")


class PassengerReservationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = make_user(username="cancel-user-1")
        cls.other = make_user(username="cancel-user-2")
        cls.flight = make_flight(code="CXFUTURE")
        cls.past_flight = make_flight(
            code="CXPAST",
            airline=cls.flight.airline,
            origin=cls.flight.from_airport,
            destination=cls.flight.to_airport,
            departs_in=-timedelta(days=1),
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def cancel(self, reservation):
        return self.client.post(reverse("bookings:cancel", args=[reservation.pk]))

    def test_owner_can_cancel_pending_reservation(self):
        reservation = make_reservation(self.flight, user=self.owner)
        response = self.cancel(reservation)
        self.assertEqual(response.status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.CANCELLED)

    def test_owner_can_cancel_approved_reservation(self):
        reservation = make_reservation(
            self.flight, user=self.owner, status=Reservation.Status.APPROVED
        )
        self.assertEqual(self.cancel(reservation).status_code, 200)

    def test_user_cannot_cancel_another_users_reservation(self):
        reservation = make_reservation(self.flight, user=self.other)
        self.assertEqual(self.cancel(reservation).status_code, 404)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.PENDING)

    def test_cannot_cancel_departed_flight_reservation(self):
        reservation = make_reservation(self.past_flight, user=self.owner)
        self.assertEqual(self.cancel(reservation).status_code, 409)

    def test_cannot_cancel_rejected_or_cancelled_reservations(self):
        for status, seat in (
            (Reservation.Status.REJECTED, "E1B"),
            (Reservation.Status.CANCELLED, "E1C"),
        ):
            reservation = make_reservation(
                self.flight, user=self.owner, seat_number=seat, status=status
            )
            with self.subTest(status=status):
                self.assertEqual(self.cancel(reservation).status_code, 409)

    def test_cancel_requires_post(self):
        reservation = make_reservation(self.flight, user=self.owner)
        response = self.client.get(reverse("bookings:cancel", args=[reservation.pk]))
        self.assertEqual(response.status_code, 405)

    def test_dashboard_lists_recent_reservations(self):
        make_reservation(self.flight, user=self.owner)
        response = self.client.get(reverse("bookings:dashboard"))
        self.assertContains(response, "CXFUTURE")

    def test_my_reservations_only_lists_own_bookings(self):
        make_reservation(self.flight, user=self.other, first_name="Somebody")
        mine = make_reservation(self.flight, user=self.owner, seat_number="E2A")
        response = self.client.get(reverse("bookings:my-reservations"))
        self.assertEqual(list(response.context["reservations"]), [mine])

    def test_owner_can_view_confirmation(self):
        reservation = make_reservation(self.flight, user=self.owner)
        response = self.client.get(
            reverse("bookings:confirmation", args=[reservation.booking_reference])
        )
        self.assertContains(response, reservation.booking_reference)


class ReservationConstraintTests(TestCase):
    def test_active_seat_must_be_unique_per_flight(self):
        flight = make_flight()
        make_reservation(flight, seat_number="E1A")
        cancelled = make_reservation(
            flight, seat_number="E1B", status=Reservation.Status.CANCELLED
        )
        cancelled.seat_number = "E1A"
        cancelled.save()
        with self.assertRaises(IntegrityError), transaction.atomic():
            make_reservation(flight, seat_number="E1A")
