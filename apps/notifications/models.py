from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(is_read=False)


class Notification(models.Model):
    class Kind(models.TextChoices):
        RESERVATION_APPROVED = "reservation_approved", "Reservation Approved"
        RESERVATION_REJECTED = "reservation_rejected", "Reservation Rejected"
        GENERAL = "general", "General Notification"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    kind = models.CharField(max_length=50, choices=Kind, default=Kind.GENERAL)
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return "%s - %s" % (self.user.username, self.title)
