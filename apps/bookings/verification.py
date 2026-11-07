import secrets

from django.utils import timezone
from django.utils.crypto import constant_time_compare

VERIFICATION_LIFETIME_SECONDS = 180
ATTEMPT_WINDOW_SECONDS = 900
MAX_ATTEMPTS = 5


class VerificationLocked(Exception):
    pass


class VerificationFailed(Exception):
    pass


class ReservationVerifier:
    answer_key = "bookings_check_answer"
    verified_key = "bookings_verified_until"
    attempts_key = "bookings_verify_attempts"
    window_key = "bookings_verify_window"

    def __init__(self, session):
        self.session = session

    def issue_check(self):
        first = secrets.randbelow(10) + 1
        second = secrets.randbelow(10) + 1
        self.session[self.answer_key] = str(first + second)
        return first, second

    def verify(self, user, password, answer):
        self.session.pop(self.verified_key, None)
        self._ensure_not_locked()
        if not password:
            self._fail("Password is required.")
        if not user.check_password(password):
            self._fail("Incorrect password. Please try again.")
        if not answer:
            self._fail("Please complete the security check.")
        expected = self.session.get(self.answer_key)
        if not expected or not constant_time_compare(str(answer).strip(), expected):
            self._fail("Incorrect answer. Please try again.")
        self.session.pop(self.answer_key, None)
        self.session.pop(self.attempts_key, None)
        self.session.pop(self.window_key, None)
        self.session[self.verified_key] = self._now() + VERIFICATION_LIFETIME_SECONDS

    def is_verified(self):
        verified_until = self.session.get(self.verified_key)
        if isinstance(verified_until, (int, float)) and self._now() < verified_until:
            return True
        self.session.pop(self.verified_key, None)
        return False

    def consume(self):
        self.session.pop(self.verified_key, None)

    def _ensure_not_locked(self):
        if self.session.get(self.attempts_key, 0) < MAX_ATTEMPTS:
            return
        if self._window_open():
            raise VerificationLocked
        self.session.pop(self.attempts_key, None)
        self.session.pop(self.window_key, None)

    def _fail(self, message):
        if not self._window_open():
            self.session[self.window_key] = self._now()
            self.session[self.attempts_key] = 0
        attempts = self.session.get(self.attempts_key, 0) + 1
        self.session[self.attempts_key] = attempts
        if attempts >= MAX_ATTEMPTS:
            raise VerificationLocked
        raise VerificationFailed(message)

    def _window_open(self):
        started = self.session.get(self.window_key)
        return (
            isinstance(started, (int, float))
            and self._now() - started < ATTEMPT_WINDOW_SECONDS
        )

    def _now(self):
        return int(timezone.now().timestamp())
