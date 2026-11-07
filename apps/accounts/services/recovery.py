from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.utils import timezone

FLOW_LIFETIME = timedelta(minutes=10)
MAX_FAILED_ATTEMPTS = 5


def normalize_security_answer(answer):
    return (answer or "").strip().casefold()


class PasswordRecoveryFlow:
    user_key = "recovery_user_id"
    verified_key = "recovery_identity_verified"
    expires_key = "recovery_expires_at"
    attempts_key = "recovery_attempts"

    def __init__(self, session):
        self.session = session

    def begin(self, identifier):
        self.clear()
        user = get_user_model().objects.find_by_login_identifier(identifier)
        eligible = user is not None and user.has_recovery_details
        self.session[self.user_key] = user.pk if eligible else 0
        self.session[self.expires_key] = (timezone.now() + FLOW_LIFETIME).timestamp()
        self.session[self.attempts_key] = 0

    def is_active(self):
        expires_at = self.session.get(self.expires_key)
        active = (
            self.user_key in self.session
            and isinstance(expires_at, (int, float))
            and timezone.now().timestamp() < expires_at
            and self.session.get(self.attempts_key, 0) < MAX_FAILED_ATTEMPTS
        )
        if not active:
            self.clear()
        return active

    def is_verified(self):
        return bool(self.session.get(self.verified_key)) and self.is_active()

    def user(self):
        user_id = self.session.get(self.user_key)
        if not user_id:
            return None
        return get_user_model().objects.filter(pk=user_id).first()

    def verify_identity(self, date_of_birth, answer):
        user = self.user()
        matches = (
            user is not None
            and date_of_birth == user.date_of_birth
            and check_password(normalize_security_answer(answer), user.security_answer)
        )
        if matches:
            self.session.cycle_key()
            self.session[self.verified_key] = True
            self.session[self.attempts_key] = 0
            return True
        self.session[self.attempts_key] = self.session.get(self.attempts_key, 0) + 1
        return False

    def clear(self):
        for key in (self.user_key, self.verified_key, self.expires_key):
            self.session.pop(key, None)
        self.session.pop(self.attempts_key, None)
