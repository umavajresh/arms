from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import make_administrator, make_user
from apps.flights.tests.factories import make_aircraft, make_flight

LAUNCHER = 'id="ai-launcher"'


class AssistantLauncherTests(TestCase):
    def test_launcher_is_offered_while_browsing(self):
        for name in ("pages:landing", "flights:search", "bookings:guest-lookup"):
            with self.subTest(page=name):
                self.assertContains(self.client.get(reverse(name)), LAUNCHER)

    def test_launcher_stays_out_of_focused_tasks(self):
        flight = make_flight(code="LCH1", aircraft=make_aircraft())
        for url in (
            reverse("accounts:login"),
            reverse("accounts:register"),
            reverse("assistant:chat"),
            reverse("bookings:seat-selection", args=[flight.pk]),
        ):
            with self.subTest(url=url):
                self.assertNotContains(self.client.get(url), LAUNCHER)

    def test_administrators_never_see_the_launcher(self):
        self.client.force_login(make_administrator())
        for name in ("console:dashboard", "tracking:tracker"):
            with self.subTest(page=name):
                self.assertNotContains(self.client.get(reverse(name)), LAUNCHER)

    def test_passengers_see_the_launcher_on_their_dashboard(self):
        self.client.force_login(make_user())
        self.assertContains(self.client.get(reverse("bookings:dashboard")), LAUNCHER)


class ErrorPageTests(TestCase):
    def test_unknown_page_uses_the_branded_template(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "We could not find that page", status_code=404)
