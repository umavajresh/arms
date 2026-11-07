from django.test import TestCase
from django.urls import reverse

from apps.accounts.tests.factories import make_user
from apps.notifications.models import Notification
from apps.notifications.services import notify


class NotificationTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.notification = notify(
            self.user, Notification.Kind.GENERAL, "Hello", "Welcome aboard"
        )

    def test_owner_can_mark_notification_read(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("notifications:mark-read", args=[self.notification.pk])
        )
        self.assertEqual(response.json()["full_message"], "Welcome aboard")
        self.notification.refresh_from_db()
        self.assertIs(self.notification.is_read, True)

    def test_other_users_cannot_read_notification(self):
        self.client.force_login(make_user(username="someone-else"))
        response = self.client.post(
            reverse("notifications:mark-read", args=[self.notification.pk])
        )
        self.assertEqual(response.status_code, 404)
