import datetime
from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.tests.factories import make_administrator
from apps.bookings.tests.factories import make_reservation
from apps.flights.models import Aircraft, Airline, Airport, Flight, FlightSchedule
from apps.flights.services.provisioning import RouteProvisioner
from apps.flights.services.schedules import ScheduleFlightGenerator

from .factories import make_aircraft, make_airline, make_airport, make_flight


class ImportDataCommandTests(TestCase):
    def test_import_data_populates_future_flights(self):
        call_command("import_data", stdout=StringIO())
        self.assertGreater(Flight.objects.count(), 0)
        self.assertIs(all(flight.is_bookable for flight in Flight.objects.all()), True)
        self.assertIs(Airline.objects.filter(code="BAW").exists(), True)
        self.assertIs(Airport.objects.filter(code="JNB").exists(), True)
        self.assertIs(Aircraft.objects.filter(code="B788").exists(), True)

    def test_import_data_is_idempotent(self):
        call_command("import_data", stdout=StringIO())
        counts = (
            Airline.objects.count(),
            Airport.objects.count(),
            Flight.objects.count(),
        )
        call_command("import_data", stdout=StringIO())
        self.assertEqual(
            counts,
            (Airline.objects.count(), Airport.objects.count(), Flight.objects.count()),
        )


class FlightSearchViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.airline = make_airline()
        cls.origin = make_airport("MAA", name="Chennai")
        cls.destination = make_airport("BLR", name="Bangalore")
        cls.day = timezone.localdate() + timedelta(days=10)

    def departure(self, hour):
        return timezone.make_aware(
            datetime.datetime.combine(self.day, datetime.time(hour))
        )

    def add_flight(self, code, hour, economy_price):
        departure = self.departure(hour)
        return Flight.objects.create(
            code=code,
            airline=self.airline,
            from_airport=self.origin,
            to_airport=self.destination,
            departure=departure,
            estimated_arrival=departure + timedelta(hours=2),
            economy_slots=10,
            business_class_slots=2,
            economy_price=economy_price,
            business_class_price=economy_price * 3,
        )

    def results(self, **filters):
        return self.client.get(
            reverse("flights:results"),
            {
                "from_airport": self.origin.pk,
                "to_airport": self.destination.pk,
                "departure_date": self.day.isoformat(),
                **filters,
            },
        )

    def test_search_page_lists_airports(self):
        response = self.client.get(reverse("flights:search"))
        self.assertContains(response, "Chennai")

    def test_invalid_search_returns_to_search_with_inputs_kept(self):
        response = self.client.get(reverse("flights:results"), {"from_airport": "x"})
        self.assertRedirects(response, reverse("flights:search") + "?from_airport=x")

    def test_same_origin_and_destination_is_explained(self):
        query = {
            "from_airport": self.origin.pk,
            "to_airport": self.origin.pk,
            "departure_date": self.day.isoformat(),
        }
        response = self.client.get(reverse("flights:results"), query, follow=True)
        self.assertContains(
            response, "Origin and destination must be different airports."
        )
        self.assertEqual(response.context["selected_from"], str(self.origin.pk))
        self.assertEqual(response.context["selected_date"], self.day.isoformat())

    def test_past_departure_date_is_rejected(self):
        yesterday = timezone.localdate() - datetime.timedelta(days=1)
        query = {
            "from_airport": self.origin.pk,
            "to_airport": self.destination.pk,
            "departure_date": yesterday.isoformat(),
        }
        response = self.client.get(reverse("flights:results"), query, follow=True)
        self.assertContains(response, "Departure date: Choose today or a later date.")

    def test_results_apply_time_window_and_price_sorting(self):
        self.add_flight("MOR1", 8, 4000)
        self.add_flight("MOR2", 9, 3000)
        self.add_flight("EVE1", 18, 2000)
        response = self.results(time_filter="morning", price_sort="asc")
        self.assertEqual(
            [f.code for f in response.context["flights"]], ["MOR2", "MOR1"]
        )
        self.assertEqual(response.context["flights"][0].available_economy, 10)

    def test_filters_are_relaxed_when_nothing_matches(self):
        self.add_flight("EVE1", 18, 2000)
        response = self.results(time_filter="morning")
        self.assertIs(response.context["filter_relaxed"], True)
        self.assertEqual(response.context["unfiltered_count"], 1)

    def test_dates_beyond_the_booking_window_are_rejected(self):
        far_future = timezone.localdate() + timedelta(days=400)
        query = {
            "from_airport": self.origin.pk,
            "to_airport": self.destination.pk,
            "departure_date": far_future.isoformat(),
        }
        with self.settings(ARMS_BOOKING_HORIZON_DAYS=365):
            response = self.client.get(reverse("flights:results"), query, follow=True)
        self.assertContains(response, "Flights open 365 days ahead.")
        self.assertIs(Flight.objects.exists(), False)

    def test_provisioner_ignores_dates_outside_the_window(self):
        far_future = timezone.localdate() + timedelta(days=30)
        with self.settings(ARMS_BOOKING_HORIZON_DAYS=7):
            created = RouteProvisioner().ensure_departures(
                self.origin, self.destination, far_future
            )
        self.assertEqual(created, 0)

    def test_route_slots_are_provisioned_for_empty_future_dates(self):
        response = self.results()
        self.assertEqual(len(response.context["flights"]), 3)
        self.assertIs(
            all(
                flight.code.startswith("ARMABL")
                for flight in response.context["flights"]
            ),
            True,
        )

    def test_availability_excludes_cancelled_reservations(self):
        flight = self.add_flight("AVL1", 8, 4000)
        make_reservation(flight, seat_number="E1A")
        make_reservation(flight, seat_number="E1B", status="cancelled")
        response = self.results()
        self.assertEqual(response.context["flights"][0].available_economy, 9)

    def test_upcoming_flights_page_lists_bookable_flights(self):
        make_flight(
            code="UPC1",
            airline=self.airline,
            origin=self.origin,
            destination=self.destination,
            departs_in=timedelta(days=1),
        )
        response = self.client.get(reverse("flights:upcoming"))
        self.assertContains(response, "UPC1")


class ScheduleGenerationTests(TestCase):
    def make_schedule(self, **fields):
        today = timezone.localdate()
        defaults = {
            "code": "SCH1",
            "airline": make_airline(),
            "from_airport": make_airport("AAA"),
            "to_airport": make_airport("BBB"),
            "aircraft": make_aircraft(),
            "departure_time": datetime.time(9, 0),
            "arrival_time": datetime.time(11, 0),
            "duration_minutes": 120,
            "start_date": today,
            "end_date": today + timedelta(days=13),
        }
        defaults.update(fields)
        return FlightSchedule.objects.create(**defaults)

    def test_weekday_schedule_skips_weekends(self):
        schedule = self.make_schedule(
            recurrence_pattern=FlightSchedule.Recurrence.WEEKDAYS
        )
        created = ScheduleFlightGenerator().generate(
            schedule, schedule.start_date, schedule.end_date
        )
        self.assertEqual(created, 10)
        self.assertIs(
            all(
                timezone.localtime(flight.departure).weekday() < 5
                for flight in Flight.objects.all()
            ),
            True,
        )

    def test_generation_is_idempotent(self):
        schedule = self.make_schedule()
        generator = ScheduleFlightGenerator()
        generator.generate(schedule, schedule.start_date, schedule.end_date)
        self.assertEqual(
            generator.generate(schedule, schedule.start_date, schedule.end_date), 0
        )

    def test_custom_schedule_uses_selected_weekdays(self):
        schedule = self.make_schedule(
            recurrence_pattern=FlightSchedule.Recurrence.CUSTOM, days_of_week="0,2"
        )
        monday = schedule.start_date + timedelta(
            days=-schedule.start_date.weekday() + 7
        )
        self.assertIs(schedule.operates_on(monday), True)
        self.assertIs(schedule.operates_on(monday + timedelta(days=1)), False)

    def test_command_generates_flights_from_active_schedules(self):
        self.make_schedule()
        call_command("generate_recurring_flights", "--days", "3", stdout=StringIO())
        self.assertEqual(Flight.objects.count(), 4)


class FlightAdminTests(TestCase):
    def test_upcoming_flights_admin_view_reports_occupancy(self):
        administrator = make_administrator()
        self.assertIs(administrator.is_staff, False)
        administrator.is_staff = True
        administrator.save()
        self.client.force_login(administrator)
        flight = make_flight(departs_in=timedelta(days=1))
        make_reservation(flight, seat_number="E1A")
        response = self.client.get(reverse("admin:flights_flight_upcoming"))
        self.assertEqual(response.status_code, 200)
        listed = response.context["flights"][0]
        self.assertEqual(listed.booked_economy, 1)
        self.assertAlmostEqual(listed.economy_occupancy, 100 / 11)
