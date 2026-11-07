from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.flights.tests.factories import make_flight
from apps.tracking.providers import LiveFlightLookup
from apps.tracking.schedule import schedule_progress


def provider_response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


AVIATIONSTACK_PAYLOAD = {
    "data": [
        {
            "flight": {"iata": "BAW123"},
            "airline": {"name": "British Airways"},
            "departure": {
                "airport": "London Heathrow",
                "scheduled": "2026-08-26T10:00",
            },
            "arrival": {"airport": "New York JFK", "scheduled": "2026-08-26T18:00"},
            "live": {
                "latitude": 51.47,
                "longitude": -0.45,
                "altitude": 6500,
                "speed_horizontal": 530,
                "updated": "2026-08-26T11:00:00+00:00",
            },
            "status": "active",
        }
    ]
}
OPENSKY_STATE = [None, "BAW123", None, None, None, -0.45, 51.47, 6500.0, None, 530.0]


class LiveFlightLookupTests(SimpleTestCase):
    @override_settings(ARMS_AVIATIONSTACK_API_KEY="demo-key")
    @patch("apps.tracking.providers.requests.get")
    def test_aviationstack_is_used_when_configured(self, get):
        get.return_value = provider_response(AVIATIONSTACK_PAYLOAD)
        result = LiveFlightLookup().find("BAW123")
        self.assertEqual(result["flight_code"], "BAW123")
        self.assertEqual(result["status"], "active")
        self.assertEqual(result["latitude"], 51.47)
        self.assertEqual(result["airline"], "British Airways")
        self.assertEqual(result["source"], "aviationstack")

    @override_settings(ARMS_AVIATIONSTACK_API_KEY="")
    @patch("apps.tracking.providers.requests.get")
    def test_opensky_is_used_without_aviationstack_key(self, get):
        get.return_value = provider_response({"states": [OPENSKY_STATE]})
        result = LiveFlightLookup().find("BAW123")
        self.assertEqual(result["source"], "opensky")
        self.assertEqual(result["longitude"], -0.45)
        get.assert_called_once()


class ScheduleProgressTests(SimpleTestCase):
    def test_phases_follow_the_schedule(self):
        now = timezone.now()
        flight = Mock(
            departure=now + timedelta(hours=1),
            estimated_arrival=now + timedelta(hours=3),
        )
        self.assertEqual(schedule_progress(flight, now), ("Boarding", 0))
        flight.departure = now - timedelta(hours=1)
        self.assertEqual(schedule_progress(flight, now)[0], "In flight")
        flight.estimated_arrival = now - timedelta(minutes=1)
        self.assertEqual(schedule_progress(flight, now), ("Landed", 100))


@override_settings(ARMS_AVIATIONSTACK_API_KEY="")
class TrackingViewTests(TestCase):
    def test_tracker_page_lists_recent_flights(self):
        make_flight(code="TRK1", departs_in=timedelta(days=1))
        self.assertContains(self.client.get(reverse("tracking:tracker")), "TRK1")

    def test_api_requires_a_flight_code(self):
        self.assertEqual(
            self.client.get(reverse("tracking:tracker-api")).status_code, 400
        )

    @patch("apps.tracking.providers.requests.get")
    def test_api_falls_back_to_schedule_data(self, get):
        get.return_value = provider_response({"states": []})
        make_flight(code="TRK2", departs_in=timedelta(days=1))
        response = self.client.get(reverse("tracking:tracker-api"), {"flight": "trk2"})
        self.assertEqual(response.json()["flight"]["status"], "Scheduled")

    @patch("apps.tracking.providers.requests.get")
    def test_api_reports_unknown_flights(self, get):
        get.return_value = provider_response({"states": []})
        response = self.client.get(reverse("tracking:tracker-api"), {"flight": "NOPE1"})
        self.assertEqual(response.status_code, 404)
