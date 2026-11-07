import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Aircraft",
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
                ("is_active", models.BooleanField(default=True)),
                ("is_archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=5)),
                ("model_name", models.CharField(max_length=250)),
                ("manufacturer", models.CharField(max_length=100)),
                ("business_capacity", models.PositiveIntegerField(default=0)),
                ("economy_capacity", models.PositiveIntegerField(default=0)),
            ],
            options={
                "verbose_name_plural": "aircraft",
                "ordering": ["model_name"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_archived", False)),
                        fields=("code",),
                        name="unique_active_aircraft_code",
                        violation_error_message="Aircraft code already exists",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="Airline",
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
                ("is_active", models.BooleanField(default=True)),
                ("is_archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=5)),
                ("name", models.CharField(max_length=250)),
                ("country", models.CharField(blank=True, max_length=100)),
                ("logo", models.ImageField(blank=True, upload_to="airlines/")),
            ],
            options={
                "ordering": ["name"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_archived", False)),
                        fields=("code",),
                        name="unique_active_airline_code",
                        violation_error_message="Airline code already exists",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("is_archived", False)),
                        fields=("name",),
                        name="unique_active_airline_name",
                        violation_error_message="Airline name already exists",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="Airport",
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
                ("is_active", models.BooleanField(default=True)),
                ("is_archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=5)),
                ("name", models.CharField(max_length=250)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("country", models.CharField(blank=True, max_length=100)),
            ],
            options={
                "ordering": ["name"],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("is_archived", False)),
                        fields=("code",),
                        name="unique_active_airport_code",
                        violation_error_message="Airport code already exists",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("is_archived", False)),
                        fields=("name",),
                        name="unique_active_airport_name",
                        violation_error_message="Airport name already exists",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="FlightSchedule",
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
                ("code", models.CharField(max_length=20)),
                ("departure_time", models.TimeField()),
                ("arrival_time", models.TimeField()),
                ("duration_minutes", models.PositiveIntegerField()),
                (
                    "recurrence_pattern",
                    models.CharField(
                        choices=[
                            ("daily", "Daily"),
                            ("weekdays", "Weekdays (Mon-Fri)"),
                            ("weekends", "Weekends (Sat-Sun)"),
                            ("weekly", "Weekly"),
                            ("custom", "Custom Pattern"),
                        ],
                        default="daily",
                        max_length=20,
                    ),
                ),
                (
                    "days_of_week",
                    models.CharField(
                        blank=True,
                        help_text="Comma-separated weekday numbers where 0 is Monday and 6 is Sunday.",
                        max_length=20,
                    ),
                ),
                (
                    "business_class_price",
                    models.DecimalField(decimal_places=2, default=0, max_digits=12),
                ),
                (
                    "economy_price",
                    models.DecimalField(decimal_places=2, default=0, max_digits=12),
                ),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("is_active", models.BooleanField(default=True)),
                ("is_archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "aircraft",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="schedules",
                        to="flights.aircraft",
                    ),
                ),
                (
                    "airline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="schedules",
                        to="flights.airline",
                    ),
                ),
                (
                    "from_airport",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scheduled_departures",
                        to="flights.airport",
                    ),
                ),
                (
                    "to_airport",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="scheduled_arrivals",
                        to="flights.airport",
                    ),
                ),
            ],
            options={
                "ordering": ["code"],
            },
        ),
        migrations.CreateModel(
            name="Flight",
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
                ("code", models.CharField(max_length=250)),
                ("departure", models.DateTimeField()),
                ("estimated_arrival", models.DateTimeField()),
                ("business_class_slots", models.PositiveIntegerField(default=0)),
                ("economy_slots", models.PositiveIntegerField(default=0)),
                (
                    "business_class_price",
                    models.DecimalField(decimal_places=2, default=0, max_digits=12),
                ),
                (
                    "economy_price",
                    models.DecimalField(decimal_places=2, default=0, max_digits=12),
                ),
                ("currency", models.CharField(default="INR", max_length=3)),
                ("is_archived", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "aircraft",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="flights",
                        to="flights.aircraft",
                    ),
                ),
                (
                    "airline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="flights",
                        to="flights.airline",
                    ),
                ),
                (
                    "from_airport",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="departing_flights",
                        to="flights.airport",
                    ),
                ),
                (
                    "to_airport",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="arriving_flights",
                        to="flights.airport",
                    ),
                ),
            ],
            options={
                "ordering": ["departure"],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            ("estimated_arrival__gt", models.F("departure"))
                        ),
                        name="flight_arrives_after_departure",
                        violation_error_message="Arrival must be after departure.",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("from_airport", models.F("to_airport")), _negated=True
                        ),
                        name="flight_route_has_distinct_airports",
                        violation_error_message="Origin and destination must differ.",
                    ),
                ],
            },
        ),
    ]
