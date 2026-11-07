import logging
import secrets
import smtplib
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger(__name__)

PASSCODE_LIFETIME = timedelta(minutes=10)
MAX_VERIFICATION_ATTEMPTS = 5


class OneTimePasscodeService:
    def issue(self, user):
        code = "%06d" % (secrets.randbelow(900000) + 100000)
        user.otp_digest = make_password(code)
        user.otp_expires_at = timezone.now() + PASSCODE_LIFETIME
        user.save(update_fields=["otp_digest", "otp_expires_at"])
        return code

    def verify(self, user, code):
        if not user.otp_digest or not user.otp_expires_at:
            return False
        if timezone.now() > user.otp_expires_at:
            self.clear(user)
            return False
        if not check_password(str(code).strip(), user.otp_digest):
            return False
        self.clear(user)
        return True

    def clear(self, user):
        user.otp_digest = ""
        user.otp_expires_at = None
        user.save(update_fields=["otp_digest", "otp_expires_at"])


class PasscodeMailer:
    subject = "Your ARMS 2.0 verification code"

    def deliver(self, user, code):
        if not user.email:
            logger.warning("User %s has no email for two-factor delivery.", user.pk)
            return False
        message = (
            "Your ARMS 2.0 verification code is %s. It expires in 10 minutes." % code
        )
        try:
            send_mail(self.subject, message, None, [user.email])
        except (smtplib.SMTPException, OSError):
            logger.exception("Unable to deliver two-factor code to user %s.", user.pk)
            return False
        return True


class TwoFactorChallenge:
    user_key = "two_factor_user_id"
    attempts_key = "two_factor_attempts"

    def __init__(self, session, passcodes=None, mailer=None):
        self.session = session
        self.passcodes = passcodes or OneTimePasscodeService()
        self.mailer = mailer or PasscodeMailer()

    def start(self, user):
        self.session[self.user_key] = user.pk
        self.session[self.attempts_key] = 0
        return self.send_code(user)

    def send_code(self, user):
        return self.mailer.deliver(user, self.passcodes.issue(user))

    def pending_user(self):
        user_id = self.session.get(self.user_key)
        if not user_id:
            return None
        return get_user_model().objects.filter(pk=user_id, is_active=True).first()

    def attempts_exhausted(self):
        attempts = self.session.get(self.attempts_key, 0) + 1
        self.session[self.attempts_key] = attempts
        return attempts > MAX_VERIFICATION_ATTEMPTS

    def verify(self, user, code):
        return self.passcodes.verify(user, code)

    def clear(self):
        self.session.pop(self.user_key, None)
        self.session.pop(self.attempts_key, None)
