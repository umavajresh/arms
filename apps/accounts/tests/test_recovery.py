from datetime import date

from django.contrib.auth.hashers import check_password
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .factories import make_recoverable_user


class PasswordRecoveryTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = make_recoverable_user(
            answer="milo",
            date_of_birth=date(1991, 4, 12),
            username="recovery-test-user",
            member_id="RECOVERY-TEST-USER",
        )

    def start(self, identifier):
        return self.client.post(
            reverse("accounts:recovery-start"), {"identifier": identifier}
        )

    def verify(self, answer, date_of_birth="1991-04-12"):
        return self.client.post(
            reverse("accounts:recovery-verify"),
            {"date_of_birth": date_of_birth, "security_answer": answer},
        )

    def test_wrong_answer_keeps_the_date_of_birth(self):
        self.start("RECOVERY-TEST-USER")
        response = self.verify("not-milo")
        self.assertContains(response, "The details did not match.")
        self.assertContains(response, 'value="1991-04-12"')

    def test_existing_and_unknown_identifiers_receive_the_same_step(self):
        for identifier in (self.user.username, "unknown-recovery-user"):
            response = self.client.post(
                reverse("accounts:recovery-start"),
                {"identifier": identifier},
                follow=True,
            )
            self.assertContains(
                response, "Your recovery question is hidden for privacy."
            )
            self.assertNotContains(response, "What is your pet")

    def test_valid_recovery_resets_password_and_clears_flow(self):
        self.assertRedirects(
            self.start("RECOVERY-TEST-USER"), reverse("accounts:recovery-verify")
        )
        self.assertRedirects(self.verify("MILO"), reverse("accounts:recovery-reset"))
        response = self.client.post(
            reverse("accounts:recovery-reset"),
            {
                "new_password1": "New-Recovery-Password-902!",
                "new_password2": "New-Recovery-Password-902!",
            },
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.user.refresh_from_db()
        self.assertIs(self.user.check_password("New-Recovery-Password-902!"), True)
        self.assertIs(check_password("milo", self.user.security_answer), True)
        self.assertNotIn("recovery_user_id", self.client.session)
        self.assertNotIn("recovery_identity_verified", self.client.session)

    def test_reset_returns_json_errors_for_ajax_requests(self):
        self.start(self.user.username)
        self.verify("milo")
        response = self.client.post(
            reverse("accounts:recovery-reset"),
            {"new_password1": "short", "new_password2": "short"},
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "failed")

    def test_reset_requires_verified_identity(self):
        self.start(self.user.username)
        response = self.client.get(reverse("accounts:recovery-reset"))
        self.assertRedirects(response, reverse("accounts:recovery-start"))

    def test_expired_flow_is_cleared(self):
        self.start(self.user.username)
        session = self.client.session
        session["recovery_expires_at"] = timezone.now().timestamp() - 1
        session.save()
        response = self.client.get(reverse("accounts:recovery-verify"))
        self.assertRedirects(response, reverse("accounts:recovery-start"))
        self.assertNotIn("recovery_user_id", self.client.session)

    def test_fifth_failed_answer_ends_the_flow(self):
        self.start(self.user.username)
        for _ in range(4):
            self.assertEqual(self.verify("incorrect").status_code, 200)
        self.assertRedirects(
            self.verify("incorrect"), reverse("accounts:recovery-start")
        )
        self.assertNotIn("recovery_user_id", self.client.session)
