from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import TravelPreference

from .factories import DEFAULT_PASSWORD, make_user


class ProfileTests(TestCase):
    def setUp(self):
        self.user = make_user(username="globetrotter", member_id="GLOBE-1")
        self.client.force_login(self.user)

    def test_profile_page_shows_account_details(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertContains(response, "GLOBE-1")
        self.assertContains(response, "Passenger")

    def test_profile_update_requires_current_password(self):
        data = {
            "first_name": "Globe",
            "last_name": "Trotter",
            "username": "globetrotter",
            "email": "globe@example.com",
            "member_id": "GLOBE-2",
            "mobile": "5550199",
        }
        rejected = self.client.post(
            reverse("accounts:profile-edit"), {**data, "current_password": "wrong"}
        )
        self.assertContains(rejected, "Password is incorrect.")
        accepted = self.client.post(
            reverse("accounts:profile-edit"),
            {**data, "current_password": DEFAULT_PASSWORD},
        )
        self.assertRedirects(accepted, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.member_id, "GLOBE-2")

    def test_update_travel_preferences(self):
        response = self.client.post(
            reverse("accounts:preferences-update"),
            {
                "preferred_language": "es",
                "preferred_currency": "EUR",
                "preferred_seat_class": "Business",
                "dietary_preference": "Vegetarian",
                "interests": "art, architecture",
                "budget_level": "luxury",
            },
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        preference = TravelPreference.objects.get(user=self.user)
        self.assertEqual(preference.preferred_language, "es")
        self.assertEqual(preference.preferred_currency, "EUR")
        self.assertEqual(preference.preferred_seat_class, "Business")
        self.assertEqual(preference.dietary_preference, "Vegetarian")
