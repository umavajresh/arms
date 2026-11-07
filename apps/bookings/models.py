import secrets

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone

from apps.flights.models import Flight

from .querysets import ReservationQuerySet


class Reservation(models.Model):
    class Cabin(models.TextChoices):
        BUSINESS = "business", "Business Class"
        ECONOMY = "economy", "Economy"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Admin Approval"
        APPROVED = "approved", "Approved by Admin"
        CANCELLED = "cancelled", "Cancelled"
        REJECTED = "rejected", "Rejected by Admin"

    class Gender(models.TextChoices):
        MALE = "Male", "Male"
        FEMALE = "Female", "Female"

    ACTIVE_STATUSES = (Status.PENDING, Status.APPROVED)

    STATUS_BADGES = {
        Status.PENDING: ("Pending Admin Approval", "warning"),
        Status.APPROVED: ("Approved - Confirmed", "success"),
        Status.CANCELLED: ("Cancelled", "secondary"),
        Status.REJECTED: ("Rejected by Admin", "danger"),
    }

    flight = models.ForeignKey(
        Flight, on_delete=models.PROTECT, related_name="reservations"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="reservations",
    )
    cabin = models.CharField(max_length=20, choices=Cabin, default=Cabin.ECONOMY)
    seat_number = models.CharField(max_length=10)
    first_name = models.CharField(max_length=250)
    middle_name = models.CharField(max_length=250, blank=True)
    last_name = models.CharField(max_length=250)
    gender = models.CharField(max_length=10, choices=Gender, default=Gender.MALE)
    email = models.EmailField(max_length=254)
    contact = models.CharField(max_length=250)
    address = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status, default=Status.PENDING)
    booking_reference = models.CharField(max_length=32, db_index=True, editable=False)
    is_guest = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReservationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["flight", "seat_number"],
                condition=Q(status__in=["pending", "approved"]),
                name="unique_active_seat_per_flight",
                violation_error_message="This seat is already reserved.",
            ),
        ]

    def __str__(self):
        return "%s - %s %s" % (self.flight.code, self.first_name, self.last_name)

    def save(self, *args, **kwargs):
        self.is_guest = self.user_id is None
        if not self.booking_reference:
            self.booking_reference = self.generate_booking_reference(self.is_guest)
        super().save(*args, **kwargs)

    @classmethod
    def generate_booking_reference(cls, is_guest):
        prefix = "GUEST" if is_guest else "ARMS"
        while True:
            token = secrets.token_hex(4).upper()
            reference = "%s-%s-%s" % (prefix, token[:4], token[4:])
            if not cls.objects.filter(booking_reference=reference).exists():
                return reference

    @property
    def full_name(self):
        return " ".join(
            part for part in (self.first_name, self.middle_name, self.last_name) if part
        )

    @property
    def status_label(self):
        return self.STATUS_BADGES[self.status][0]

    @property
    def status_badge(self):
        return self.STATUS_BADGES[self.status][1]

    @property
    def is_active(self):
        return self.status in self.ACTIVE_STATUSES

    @property
    def has_departed(self):
        return self.flight.departure <= timezone.now()

    @property
    def can_cancel(self):
        return self.is_active and not self.has_departed

    @property
    def can_be_approved(self):
        return self.status == self.Status.PENDING and not self.has_departed

    @property
    def cancellation_status(self):
        if self.status == self.Status.CANCELLED:
            return "Already cancelled"
        if self.status == self.Status.REJECTED:
            return "Rejected by admin"
        if self.has_departed:
            return "Flight has departed"
        return "Can cancel"
