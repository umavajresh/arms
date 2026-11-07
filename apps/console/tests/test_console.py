from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import make_administrator, make_user
from apps.bookings.models import Reservation
from apps.bookings.tests.factories import make_reservation
from apps.flights.models import Aircraft, Airline, Airport, Flight
from apps.flights.tests.factories import (
    make_aircraft,
    make_airline,
    make_airport,
    make_flight,
)
from apps.notifications.models import Notification

ARCHIVE_ROUTES = (
    "console:airline-archive",
    "console:airport-archive",
    "console:aircraft-archive",
    "console:flight-archive",
)


class ConsoleAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.passenger = make_user(username="route-test-passenger")

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("console:aircraft-list"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_passenger_cannot_open_console_pages(self):
        self.client.force_login(self.passenger)
        for route in (
            "console:dashboard",
            "console:airline-list",
            "console:airport-list",
            "console:aircraft-list",
            "console:flight-list",
            "console:reservation-list",
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertRedirects(response, reverse("bookings:dashboard"))

    def test_passenger_cannot_open_management_forms(self):
        self.client.force_login(self.passenger)
        for route in (
            "console:airline-update",
            "console:airport-update",
            "console:flight-update",
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=[1]))
                self.assertRedirects(response, reverse("bookings:dashboard"))

    def test_passenger_cannot_execute_modifications(self):
        self.client.force_login(self.passenger)
        for route, args in (
            ("console:airline-create", []),
            ("console:airport-create", []),
            ("console:flight-create", []),
            ("console:aircraft-create", []),
            *[(route, [1]) for route in ARCHIVE_ROUTES],
            ("console:reservation-status", [1]),
            ("console:reservation-delete", [1]),
        ):
            with self.subTest(route=route):
                response = self.client.post(reverse(route, args=args), {"code": "UA1"})
                self.assertRedirects(response, reverse("bookings:dashboard"))
        self.assertIs(Aircraft.objects.exists(), False)

    def test_passenger_ajax_requests_receive_403(self):
        self.client.force_login(self.passenger)
        response = self.client.post(
            reverse("console:airline-create"),
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 403)


class ConsoleManagementTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_administrator()

    def setUp(self):
        self.client.force_login(self.admin)

    def test_dashboard_shows_counts(self):
        make_flight()
        response = self.client.get(reverse("console:dashboard"))
        self.assertEqual(response.context["flight"], 1)
        self.assertEqual(response.context["airport"], 2)

    def test_create_and_update_airline(self):
        form = self.client.get(reverse("console:airline-create"))
        self.assertContains(form, 'name="code"')
        created = self.client.post(
            reverse("console:airline-create"),
            {"code": "NWA", "name": "New Air", "country": "India", "is_active": "True"},
        )
        self.assertEqual(created.json()["status"], "success")
        airline = Airline.objects.get(code="NWA")
        updated = self.client.post(
            reverse("console:airline-update", args=[airline.pk]),
            {"code": "NWA", "name": "Newer Air", "is_active": "False"},
        )
        self.assertEqual(updated.json()["status"], "success")
        airline.refresh_from_db()
        self.assertEqual(airline.name, "Newer Air")
        self.assertIs(airline.is_active, False)

    def test_duplicate_active_codes_are_rejected_but_archived_codes_are_reusable(self):
        make_airport("DUP")
        duplicate = self.client.post(
            reverse("console:airport-create"),
            {"code": "DUP", "name": "Other", "is_active": "True"},
        )
        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("Airport code already exists", duplicate.json()["msg"])
        Airport.objects.filter(code="DUP").update(is_archived=True)
        reused = self.client.post(
            reverse("console:airport-create"),
            {"code": "DUP", "name": "Reused", "is_active": "True"},
        )
        self.assertEqual(reused.status_code, 200)

    def test_create_aircraft(self):
        response = self.client.post(
            reverse("console:aircraft-create"),
            {
                "code": "A20N",
                "model_name": "Airbus A320neo",
                "manufacturer": "Airbus",
                "business_capacity": "8",
                "economy_capacity": "150",
                "is_active": "True",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Aircraft.objects.get(code="A20N").economy_capacity, 150)

    def test_create_flight_copies_aircraft_capacity(self):
        airline = make_airline()
        origin, destination = make_airport("AAA"), make_airport("BBB")
        aircraft = make_aircraft(business_capacity=6, economy_capacity=60)
        response = self.client.post(
            reverse("console:flight-create"),
            {
                "code": "NF100",
                "airline": airline.pk,
                "from_airport": origin.pk,
                "to_airport": destination.pk,
                "aircraft": aircraft.pk,
                "departure": "2099-01-01T08:00",
                "estimated_arrival": "2099-01-01T10:00",
                "business_class_price": "9000",
                "economy_price": "3000",
            },
        )
        self.assertEqual(response.status_code, 200)
        flight = Flight.objects.get(code="NF100")
        self.assertEqual(flight.economy_slots, 60)
        self.assertEqual(flight.currency, "INR")

    def test_flight_with_identical_airports_is_rejected(self):
        airport = make_airport("SAM")
        response = self.client.post(
            reverse("console:flight-create"),
            {
                "code": "BAD1",
                "airline": make_airline().pk,
                "from_airport": airport.pk,
                "to_airport": airport.pk,
                "aircraft": make_aircraft().pk,
                "departure": "2099-01-01T08:00",
                "estimated_arrival": "2099-01-01T10:00",
                "business_class_price": "1",
                "economy_price": "1",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Origin and destination must differ.", response.json()["msg"])

    def test_archive_endpoints_reject_get_requests(self):
        for route in (*ARCHIVE_ROUTES, "console:reservation-delete"):
            with self.subTest(route=route):
                response = self.client.get(reverse(route, args=[1]))
                self.assertEqual(response.status_code, 405)

    def test_archiving_aircraft_preserves_flights_and_reservations(self):
        aircraft = make_aircraft(code="ZTEST", business_capacity=2, economy_capacity=8)
        flight = make_flight(aircraft=aircraft)
        reservation = make_reservation(flight)
        response = self.client.post(
            reverse("console:aircraft-archive", args=[aircraft.pk])
        )
        self.assertEqual(response.status_code, 200)
        aircraft.refresh_from_db()
        self.assertIs(aircraft.is_archived, True)
        self.assertIs(Flight.objects.filter(pk=flight.pk).exists(), True)
        self.assertIs(Reservation.objects.filter(pk=reservation.pk).exists(), True)
        again = self.client.post(
            reverse("console:aircraft-archive", args=[aircraft.pk])
        )
        self.assertEqual(again.status_code, 404)

    def test_reservation_status_transitions(self):
        passenger = make_user()
        reservation = make_reservation(make_flight(), user=passenger)
        url = reverse("console:reservation-status", args=[reservation.pk])
        self.assertEqual(self.client.post(url, {"status": "99"}).status_code, 400)
        self.assertEqual(self.client.post(url, {"status": "approved"}).status_code, 200)
        reservation.refresh_from_db()
        self.assertEqual(reservation.status, Reservation.Status.APPROVED)
        self.assertEqual(self.client.post(url, {"status": "approved"}).status_code, 409)
        notification = Notification.objects.get(user=passenger)
        self.assertEqual(notification.kind, Notification.Kind.RESERVATION_APPROVED)
        self.assertEqual(
            self.client.post(url, {"status": "cancelled"}).status_code, 200
        )
        self.assertEqual(
            self.client.post(url, {"status": "cancelled"}).status_code, 409
        )

    def test_reservation_detail_and_delete(self):
        reservation = make_reservation(make_flight())
        detail = self.client.get(
            reverse("console:reservation-detail", args=[reservation.pk])
        )
        self.assertContains(detail, reservation.full_name)
        deleted = self.client.post(
            reverse("console:reservation-delete", args=[reservation.pk])
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertIs(Reservation.objects.exists(), False)
