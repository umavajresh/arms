from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.urls import reverse

from .managers import UserManager


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMINISTRATOR = "administrator", "Administrator"
        PASSENGER = "passenger", "Passenger"

    class SecurityQuestion(models.TextChoices):
        NICKNAME = "nickname", "What is your nickname?"
        PET = "pet", "What is your pet's name?"
        BIRTHPLACE = "birthplace", "What is your place of birth?"
        MOTHER_MAIDEN = "mother_maiden", "What is your mother's maiden name?"
        FIRST_SCHOOL = "first_school", "What was the name of your first school?"
        FIRST_CAR = "first_car", "What was your first car?"
        CHILDHOOD_FRIEND = (
            "childhood_friend",
            "What is the name of your childhood best friend?",
        )

    member_id = models.CharField(
        "User ID", max_length=50, unique=True, null=True, blank=True
    )
    mobile = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role, default=Role.PASSENGER)
    date_of_birth = models.DateField(null=True, blank=True)
    security_question = models.CharField(
        max_length=50, choices=SecurityQuestion, blank=True
    )
    security_answer = models.CharField(max_length=128, blank=True)
    two_factor_enabled = models.BooleanField(default=False)
    otp_digest = models.CharField(max_length=128, blank=True)
    otp_expires_at = models.DateTimeField(null=True, blank=True)

    objects = UserManager()

    @property
    def is_administrator(self):
        return self.role == self.Role.ADMINISTRATOR

    @property
    def masked_email(self):
        name, separator, domain = self.email.partition("@")
        if not separator:
            return ""
        visible = name[0] + "***" if len(name) > 1 else "***"
        return "%s@%s" % (visible, domain)

    @property
    def has_recovery_details(self):
        return bool(
            self.security_question and self.security_answer and self.date_of_birth
        )

    def get_dashboard_url(self):
        if self.is_administrator:
            return reverse("console:dashboard")
        return reverse("bookings:dashboard")


class TravelPreference(models.Model):
    class Language(models.TextChoices):
        ENGLISH = "en", "English (EN)"
        SPANISH = "es", "Spanish (Español)"
        FRENCH = "fr", "French (Français)"
        GERMAN = "de", "German (Deutsch)"
        JAPANESE = "ja", "Japanese (日本語)"
        HINDI = "hi", "Hindi (हिन्दी)"

    class Currency(models.TextChoices):
        USD = "USD", "USD ($)"
        EUR = "EUR", "EUR (€)"
        GBP = "GBP", "GBP (£)"
        JPY = "JPY", "JPY (¥)"
        INR = "INR", "INR (₹)"

    class SeatClass(models.TextChoices):
        ECONOMY = "Economy", "Economy"
        BUSINESS = "Business", "Business Class"

    class BudgetLevel(models.TextChoices):
        ECONOMY = "economy", "Budget / Economy"
        MODERATE = "moderate", "Moderate"
        LUXURY = "luxury", "Luxury"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="travel_preference",
    )
    preferred_language = models.CharField(
        max_length=10, choices=Language, default=Language.ENGLISH
    )
    preferred_currency = models.CharField(
        max_length=10, choices=Currency, default=Currency.USD
    )
    preferred_seat_class = models.CharField(
        max_length=20, choices=SeatClass, default=SeatClass.ECONOMY
    )
    dietary_preference = models.CharField(max_length=50, blank=True)
    interests = models.CharField(max_length=255, blank=True)
    budget_level = models.CharField(
        max_length=20, choices=BudgetLevel, default=BudgetLevel.MODERATE
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return "Preferences for %s" % self.user.username
