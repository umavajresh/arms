import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("flights", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Reservation",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "cabin",
                    models.CharField(
                        choices=[
                            ("business", "Business Class"),
                            ("economy", "Economy"),
                        ],
                        default="economy",
                        max_length=20,
                    ),
                ),
                ("seat_number", models.CharField(max_length=10)),
                ("first_name", models.CharField(max_length=250)),
                ("middle_name", models.CharField(blank=True, max_length=250)),
                ("last_name", models.CharField(max_length=250)),
                (
                    "gender",
                    models.CharField(
                        choices=[("Male", "Male"), ("Female", "Female")],
                        default="Male",
                        max_length=10,
                    ),
                ),
                ("email", models.EmailField(max_length=254)),
                ("contact", models.CharField(max_length=250)),
                ("address", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending Admin Approval"),
                            ("approved", "Approved by Admin"),
                            ("cancelled", "Cancelled"),
                            ("rejected", "Rejected by Admin"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                (
                    "booking_reference",
                    models.CharField(editable=False, max_length=32, unique=True),
                ),
                ("is_guest", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "flight",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reservations",
                        to="flights.flight",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="reservations",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("status__in", ["pending", "approved"])),
                        fields=("flight", "seat_number"),
                        name="unique_active_seat_per_flight",
                        violation_error_message="This seat is already reserved.",
                    )
                ],
            },
        ),
    ]
