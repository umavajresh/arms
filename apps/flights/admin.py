import datetime

from django.contrib import admin
from django.db.models import Q
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone

from apps.bookings.selectors import occupancy_percent, with_seat_availability

from .models import Aircraft, Airline, Airport, Flight, FlightSchedule
from .services.schedules import ScheduleFlightGenerator

UPCOMING_DAY_OPTIONS = (1, 3, 7, 14, 30)
UPCOMING_SORTS = {
    "departure": lambda flight: flight.departure,
    "code": lambda flight: flight.code,
    "airline": lambda flight: flight.airline.name,
    "from_airport": lambda flight: flight.from_airport.code,
    "to_airport": lambda flight: flight.to_airport.code,
}
UPCOMING_DESCENDING_SORTS = {
    "occupancy": lambda flight: flight.overall_occupancy,
    "reservation_count": lambda flight: flight.reservation_count,
}


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value or "")
    except ValueError:
        return None


def _parse_days(value):
    return int(value) if (value or "").isdecimal() and 0 < int(value) <= 365 else 7


@admin.register(Airline)
class AirlineAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "country", "is_active", "is_archived")
    list_filter = ("is_active", "is_archived")
    search_fields = ("code", "name", "country")


@admin.register(Airport)
class AirportAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "city", "country", "is_active", "is_archived")
    list_filter = ("is_active", "is_archived", "country")
    search_fields = ("code", "name", "city", "country")


@admin.register(Aircraft)
class AircraftAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "model_name",
        "business_capacity",
        "economy_capacity",
        "is_active",
    )
    list_filter = ("is_active", "is_archived")
    search_fields = ("code", "model_name")


@admin.register(Flight)
class FlightAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "airline",
        "from_airport",
        "to_airport",
        "departure",
        "estimated_arrival",
    )
    list_filter = ("airline", "from_airport", "to_airport", "is_archived")
    search_fields = ("code", "airline__name", "from_airport__name", "to_airport__name")
    list_select_related = ("airline", "from_airport", "to_airport")
    date_hierarchy = "departure"

    def get_urls(self):
        upcoming = [
            path(
                "upcoming/",
                self.admin_site.admin_view(self.upcoming_view),
                name="flights_flight_upcoming",
            ),
        ]
        return upcoming + super().get_urls()

    def upcoming_view(self, request):
        days = _parse_days(request.GET.get("days"))
        start = _parse_date(request.GET.get("date_from")) or timezone.localdate()
        end = _parse_date(request.GET.get("date_to")) or start + datetime.timedelta(
            days=days
        )
        filters = {
            "airline": request.GET.get("airline", ""),
            "airport": request.GET.get("airport", ""),
            "aircraft": request.GET.get("aircraft", ""),
        }
        flights = Flight.objects.unarchived().with_route()
        flights = flights.departing_between(start, end)
        if filters["airline"].isdecimal():
            flights = flights.filter(airline_id=filters["airline"])
        if filters["airport"].isdecimal():
            flights = flights.filter(
                Q(from_airport_id=filters["airport"])
                | Q(to_airport_id=filters["airport"])
            )
        if filters["aircraft"].isdecimal():
            flights = flights.filter(aircraft_id=filters["aircraft"])
        flights = list(with_seat_availability(flights))
        for flight in flights:
            flight.economy_occupancy = occupancy_percent(
                flight.booked_economy, flight.economy_slots
            )
            flight.business_occupancy = occupancy_percent(
                flight.booked_business, flight.business_class_slots
            )
            flight.overall_occupancy = occupancy_percent(
                flight.booked_economy + flight.booked_business,
                flight.economy_slots + flight.business_class_slots,
            )
        sort_by = request.GET.get("sort", "departure")
        if sort_by in UPCOMING_DESCENDING_SORTS:
            flights.sort(key=UPCOMING_DESCENDING_SORTS[sort_by], reverse=True)
        else:
            flights.sort(key=UPCOMING_SORTS.get(sort_by, UPCOMING_SORTS["departure"]))
        context = {
            **self.admin_site.each_context(request),
            "title": "Upcoming Flights",
            "topbar": True,
            "opts": self.model._meta,
            "flights": flights,
            "total_reservations": sum(flight.reservation_count for flight in flights),
            "today": start,
            "end_date": end,
            "days": days,
            "days_options": UPCOMING_DAY_OPTIONS,
            "airlines": Airline.objects.available(),
            "airports": Airport.objects.available(),
            "aircraft": Aircraft.objects.available(),
            "schedules": FlightSchedule.objects.select_related(
                "airline", "aircraft", "from_airport", "to_airport"
            ).filter(is_active=True, is_archived=False, end_date__gte=start),
            "selected_airline": filters["airline"],
            "selected_airport": filters["airport"],
            "selected_aircraft": filters["aircraft"],
            "date_from": request.GET.get("date_from", ""),
            "date_to": request.GET.get("date_to", ""),
            "sort_by": sort_by,
        }
        return TemplateResponse(request, "admin/flights/flight/upcoming.html", context)


@admin.register(FlightSchedule)
class FlightScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "airline",
        "from_airport",
        "to_airport",
        "recurrence_pattern",
        "start_date",
        "end_date",
        "is_active",
    )
    list_filter = ("airline", "recurrence_pattern", "is_active")
    search_fields = ("code", "airline__name", "from_airport__name", "to_airport__name")
    date_hierarchy = "start_date"
    actions = ["generate_flights", "activate_schedules", "deactivate_schedules"]
    fieldsets = (
        (
            "Flight Information",
            {"fields": ("code", "airline", "from_airport", "to_airport", "aircraft")},
        ),
        (
            "Schedule",
            {"fields": ("departure_time", "arrival_time", "duration_minutes")},
        ),
        (
            "Recurrence",
            {
                "fields": (
                    "recurrence_pattern",
                    "days_of_week",
                    "start_date",
                    "end_date",
                )
            },
        ),
        ("Pricing", {"fields": ("business_class_price", "economy_price", "currency")}),
        ("Status", {"fields": ("is_active", "is_archived")}),
    )

    @admin.action(description="Generate flights for the next 30 days")
    def generate_flights(self, request, queryset):
        generator = ScheduleFlightGenerator()
        created = sum(generator.generate_upcoming(schedule) for schedule in queryset)
        self.message_user(
            request,
            "Generated %d flights for %d schedules." % (created, queryset.count()),
        )

    @admin.action(description="Activate selected schedules")
    def activate_schedules(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, "%d schedules have been activated." % updated)

    @admin.action(description="Deactivate selected schedules")
    def deactivate_schedules(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, "%d schedules have been deactivated." % updated)
