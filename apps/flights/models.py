from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from .querysets import FlightQuerySet, ReferenceDataQuerySet


class ReferenceData(models.Model):
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ReferenceDataQuerySet.as_manager()

    class Meta:
        abstract = True


class Airline(ReferenceData):
    code = models.CharField(max_length=5)
    name = models.CharField(max_length=250)
    country = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to="airlines/", blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(is_archived=False),
                name="unique_active_airline_code",
                violation_error_message="Airline code already exists",
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(is_archived=False),
                name="unique_active_airline_name",
                violation_error_message="Airline name already exists",
            ),
        ]

    def __str__(self):
        return "%s - %s" % (self.code, self.name)


class Airport(ReferenceData):
    code = models.CharField(max_length=5)
    name = models.CharField(max_length=250)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(is_archived=False),
                name="unique_active_airport_code",
                violation_error_message="Airport code already exists",
            ),
            models.UniqueConstraint(
                fields=["name"],
                condition=Q(is_archived=False),
                name="unique_active_airport_name",
                violation_error_message="Airport name already exists",
            ),
        ]

    def __str__(self):
        return "%s - %s" % (self.code, self.name)


class Aircraft(ReferenceData):
    code = models.CharField(max_length=5)
    model_name = models.CharField(max_length=250)
    manufacturer = models.CharField(max_length=100)
    business_capacity = models.PositiveIntegerField(default=0)
    economy_capacity = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["model_name"]
        verbose_name_plural = "aircraft"
        constraints = [
            models.UniqueConstraint(
                fields=["code"],
                condition=Q(is_archived=False),
                name="unique_active_aircraft_code",
                violation_error_message="Aircraft code already exists",
            ),
        ]

    def __str__(self):
        return "%s - %s" % (self.code, self.model_name)


class Flight(models.Model):
    code = models.CharField(max_length=250)
    airline = models.ForeignKey(
        Airline, on_delete=models.PROTECT, related_name="flights"
    )
    from_airport = models.ForeignKey(
        Airport, on_delete=models.PROTECT, related_name="departing_flights"
    )
    to_airport = models.ForeignKey(
        Airport, on_delete=models.PROTECT, related_name="arriving_flights"
    )
    aircraft = models.ForeignKey(
        Aircraft,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="flights",
    )
    departure = models.DateTimeField()
    estimated_arrival = models.DateTimeField()
    business_class_slots = models.PositiveIntegerField(default=0)
    economy_slots = models.PositiveIntegerField(default=0)
    business_class_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    economy_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="INR")
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = FlightQuerySet.as_manager()

    class Meta:
        ordering = ["departure"]
        constraints = [
            models.CheckConstraint(
                condition=Q(estimated_arrival__gt=F("departure")),
                name="flight_arrives_after_departure",
                violation_error_message="Arrival must be after departure.",
            ),
            models.CheckConstraint(
                condition=~Q(from_airport=F("to_airport")),
                name="flight_route_has_distinct_airports",
                violation_error_message="Origin and destination must differ.",
            ),
        ]

    def __str__(self):
        return "%s [%s - %s]" % (
            self.code,
            self.from_airport.name,
            self.to_airport.name,
        )

    def save(self, *args, **kwargs):
        if self.aircraft_id:
            self.business_class_slots = self.aircraft.business_capacity
            self.economy_slots = self.aircraft.economy_capacity
        super().save(*args, **kwargs)

    @property
    def is_bookable(self):
        return not self.is_archived and self.departure > timezone.now()


class FlightSchedule(models.Model):
    class Recurrence(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKDAYS = "weekdays", "Weekdays (Mon-Fri)"
        WEEKENDS = "weekends", "Weekends (Sat-Sun)"
        WEEKLY = "weekly", "Weekly"
        CUSTOM = "custom", "Custom Pattern"

    code = models.CharField(max_length=20)
    airline = models.ForeignKey(
        Airline, on_delete=models.PROTECT, related_name="schedules"
    )
    from_airport = models.ForeignKey(
        Airport, on_delete=models.PROTECT, related_name="scheduled_departures"
    )
    to_airport = models.ForeignKey(
        Airport, on_delete=models.PROTECT, related_name="scheduled_arrivals"
    )
    aircraft = models.ForeignKey(
        Aircraft, on_delete=models.PROTECT, related_name="schedules"
    )
    departure_time = models.TimeField()
    arrival_time = models.TimeField()
    duration_minutes = models.PositiveIntegerField()
    recurrence_pattern = models.CharField(
        max_length=20, choices=Recurrence, default=Recurrence.DAILY
    )
    days_of_week = models.CharField(
        max_length=20,
        blank=True,
        help_text="Comma-separated weekday numbers where 0 is Monday and 6 is Sunday.",
    )
    business_class_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0
    )
    economy_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=3, default="INR")
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return "%s: %s to %s (%s)" % (
            self.code,
            self.from_airport.code,
            self.to_airport.code,
            self.recurrence_pattern,
        )

    @property
    def weekdays(self):
        return [int(day) for day in self.days_of_week.split(",") if day.strip()]

    def operates_on(self, day):
        if not self.start_date <= day <= self.end_date:
            return False
        weekday = day.weekday()
        rules = {
            self.Recurrence.DAILY: lambda: True,
            self.Recurrence.WEEKDAYS: lambda: weekday < 5,
            self.Recurrence.WEEKENDS: lambda: weekday >= 5,
            self.Recurrence.WEEKLY: lambda: self.weekdays[:1] == [weekday],
            self.Recurrence.CUSTOM: lambda: weekday in self.weekdays,
        }
        rule = rules.get(self.recurrence_pattern)
        return bool(rule and rule())
