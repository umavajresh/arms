import re
import smtplib
from unittest.mock import patch

from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User

from .factories import DEFAULT_PASSWORD, make_administrator, make_user


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_user(username="login-test-user", member_id="LOGIN-TEST-42")

    def login(self, client, identifier, password=DEFAULT_PASSWORD, **extra):
        return client.post(
            reverse("accounts:login"),
            {"username": identifier, "password": password, **extra},
        )

    def test_username_and_member_id_create_independent_one_day_sessions(self):
        clients = (Client(), Client())
        for client, identifier in zip(clients, (self.user.username, "LOGIN-TEST-42")):
            response = self.login(client, identifier)
            self.assertEqual(response.json()["status"], "success")
            self.assertEqual(response.cookies["sessionid"]["max-age"], 86400)
        for client in clients:
            self.assertEqual(client.session["_auth_user_id"], str(self.user.pk))

    def test_passenger_is_redirected_to_passenger_dashboard(self):
        response = self.login(self.client, self.user.username)
        self.assertEqual(response.json()["redirect"], reverse("bookings:dashboard"))

    def test_administrator_is_redirected_to_console(self):
        make_administrator(username="console-admin")
        response = self.login(self.client, "console-admin")
        self.assertEqual(response.json()["redirect"], reverse("console:dashboard"))

    def test_safe_next_url_is_honoured(self):
        next_url = reverse("bookings:my-reservations")
        response = self.login(self.client, self.user.username, next=next_url)
        self.assertEqual(response.json()["redirect"], next_url)

    def test_external_next_url_is_ignored(self):
        response = self.login(
            self.client, self.user.username, next="https://evil.test/"
        )
        self.assertEqual(response.json()["redirect"], reverse("bookings:dashboard"))

    def test_wrong_password_is_rejected(self):
        response = self.login(self.client, self.user.username, password="wrong")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["msg"], "Incorrect User ID or password")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_post_and_ends_session(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("accounts:logout")).status_code, 405)
        response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(response, reverse("pages:landing"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_protected_pages_redirect_anonymous_users_to_login(self):
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_protected_json_endpoints_return_401_for_anonymous_ajax(self):
        response = self.client.post(
            reverse("bookings:verify"), headers={"x-requested-with": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 401)


class RegistrationTests(TestCase):
    def registration_data(self, **overrides):
        return {
            "first_name": "Test",
            "last_name": "Passenger",
            "email": "test.passenger@example.com",
            "member_id": "TEST-USER-2026",
            "mobile": "5550101",
            "username": "test-passenger-2026",
            "date_of_birth": "1990-01-02",
            "security_question": "nickname",
            "security_answer": "Test Answer",
            "password1": "Registration-Test-Password-42",
            "password2": "Registration-Test-Password-42",
            **overrides,
        }

    def test_registration_creates_a_passenger_that_can_log_in(self):
        page = self.client.get(reverse("accounts:register"))
        self.assertContains(page, 'action="%s"' % reverse("accounts:register"))
        response = self.client.post(
            reverse("accounts:register"), self.registration_data()
        )
        self.assertEqual(response.json()["status"], "success")
        user = User.objects.get(username="test-passenger-2026")
        self.assertIs(user.check_password("Registration-Test-Password-42"), True)
        self.assertEqual(user.member_id, "TEST-USER-2026")
        self.assertEqual(user.role, User.Role.PASSENGER)
        self.assertNotEqual(user.security_answer, "test answer")
        login = self.client.post(
            reverse("accounts:login"),
            {"username": "TEST-USER-2026", "password": "Registration-Test-Password-42"},
        )
        self.assertEqual(login.json()["status"], "success")

    def test_duplicate_member_id_is_reported(self):
        make_user(username="existing", member_id="TEST-USER-2026")
        response = self.client.post(
            reverse("accounts:register"), self.registration_data()
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["msg"], "User ID: User with this User ID already exists."
        )


class TwoFactorTests(TestCase):
    def setUp(self):
        self.user = make_user(
            username="twofa_user",
            email="twofa@example.com",
            first_name="TwoFa",
            two_factor_enabled=True,
        )

    def start_challenge(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "twofa_user", "password": DEFAULT_PASSWORD},
        )
        return response, re.search(r"\b(\d{6})\b", mail.outbox[-1].body).group(1)

    def test_login_requires_second_factor_and_emails_code(self):
        response, code = self.start_challenge()
        self.assertEqual(response.json()["status"], "2fa_required")
        self.assertEqual(
            response.json()["redirect"], reverse("accounts:two-factor-verify")
        )
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(mail.outbox[-1].to, ["twofa@example.com"])
        self.assertEqual(len(code), 6)
        self.user.refresh_from_db()
        self.assertNotEqual(self.user.otp_digest, code)

    @patch(
        "apps.accounts.services.two_factor.send_mail",
        side_effect=smtplib.SMTPException,
    )
    def test_undeliverable_code_is_reported_at_sign_in(self, send_mail):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "twofa_user", "password": DEFAULT_PASSWORD},
        )
        self.assertEqual(response.status_code, 503)
        self.assertIn("could not email your verification code", response.json()["msg"])
        self.assertNotIn("two_factor_user_id", self.client.session)

    def test_valid_code_signs_in(self):
        _, code = self.start_challenge()
        response = self.client.post(
            reverse("accounts:two-factor-verify"), {"otp_code": code}
        )
        self.assertRedirects(response, reverse("bookings:dashboard"))
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))
        self.user.refresh_from_db()
        self.assertEqual(self.user.otp_digest, "")

    def test_invalid_code_is_rejected(self):
        self.start_challenge()
        response = self.client.post(
            reverse("accounts:two-factor-verify"), {"otp_code": "999999"}
        )
        self.assertContains(response, "Invalid or expired verification code")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_expired_code_is_rejected(self):
        _, code = self.start_challenge()
        User.objects.filter(pk=self.user.pk).update(otp_expires_at="2000-01-01T00:00Z")
        response = self.client.post(
            reverse("accounts:two-factor-verify"), {"otp_code": code}
        )
        self.assertContains(response, "Invalid or expired verification code")

    def test_sixth_attempt_locks_the_challenge(self):
        self.start_challenge()
        for _ in range(5):
            self.client.post(reverse("accounts:two-factor-verify"), {"otp_code": "0"})
        response = self.client.post(
            reverse("accounts:two-factor-verify"), {"otp_code": "000000"}
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("two_factor_user_id", self.client.session)

    def test_resend_issues_a_new_code(self):
        self.start_challenge()
        response = self.client.post(reverse("accounts:two-factor-resend"))
        self.assertRedirects(response, reverse("accounts:two-factor-verify"))
        self.assertEqual(len(mail.outbox), 2)

    def test_verify_page_without_challenge_redirects_to_login(self):
        response = self.client.get(reverse("accounts:two-factor-verify"))
        self.assertRedirects(response, reverse("accounts:login"))

    def test_toggle_switches_two_factor_state(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("accounts:two-factor-toggle"))
        self.assertRedirects(response, reverse("accounts:profile"))
        self.user.refresh_from_db()
        self.assertIs(self.user.two_factor_enabled, False)
        self.client.post(reverse("accounts:two-factor-toggle"))
        self.user.refresh_from_db()
        self.assertIs(self.user.two_factor_enabled, True)
