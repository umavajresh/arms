from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import make_administrator, make_user
from apps.flights.tests.factories import make_airport


class PublicPageTests(TestCase):
    def test_terms_of_service_page(self):
        response = self.client.get(reverse("pages:terms"))
        self.assertContains(response, "Terms of Service")
        self.assertContains(response, "ARMS 2.0")

    def test_privacy_policy_page(self):
        response = self.client.get(reverse("pages:privacy"))
        self.assertContains(response, "Privacy Policy")
        self.assertContains(response, "Data Minimization")

    def test_landing_page_lists_active_airports(self):
        make_airport("MAA", name="Chennai International")
        response = self.client.get(reverse("pages:landing"))
        self.assertContains(response, "Chennai International")

    def test_signed_in_users_are_sent_to_their_dashboard(self):
        self.client.force_login(make_user())
        self.assertRedirects(
            self.client.get(reverse("pages:landing")), reverse("bookings:dashboard")
        )
        self.client.force_login(make_administrator())
        self.assertRedirects(
            self.client.get(reverse("pages:landing")), reverse("console:dashboard")
        )
