import datetime

from django.contrib import admin, messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path
from django.views.decorators.http import require_POST

from apps.flights.models import Flight

from .models import Reservation
from .services import ReservationDecisionService


def _parse_date(value):
    try:
        return datetime.date.fromisoformat(value or "")
    except ValueError:
        return None


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    list_display = (
        "booking_reference",
        "user",
        "flight",
        "cabin",
        "seat_number",
        "status",
    )
    list_filter = ("status", "cabin", "is_guest")
    search_fields = (
        "booking_reference",
        "flight__code",
        "user__username",
        "first_name",
        "last_name",
    )
    list_select_related = ("flight", "user")
    change_list_template = "admin/bookings/reservation/change_list.html"

    def get_urls(self):
        approval = [
            path(
                "approval/",
                self.admin_site.admin_view(self.approval_view),
                name="bookings_reservation_approval",
            ),
            path(
                "<int:pk>/approve/",
                self.admin_site.admin_view(require_POST(self.approve_view)),
                name="bookings_reservation_approve",
            ),
            path(
                "<int:pk>/reject/",
                self.admin_site.admin_view(require_POST(self.reject_view)),
                name="bookings_reservation_reject",
            ),
        ]
        return approval + super().get_urls()

    def approval_view(self, request):
        status = request.GET.get("status", Reservation.Status.PENDING)
        flight_id = request.GET.get("flight", "")
        date_from = _parse_date(request.GET.get("date_from"))
        date_to = _parse_date(request.GET.get("date_to"))
        reservations = Reservation.objects.with_flight().select_related("user")
        if status in Reservation.Status.values:
            reservations = reservations.filter(status=status)
        if flight_id.isdecimal():
            reservations = reservations.filter(flight_id=flight_id)
        if date_from:
            reservations = reservations.filter(created_at__date__gte=date_from)
        if date_to:
            reservations = reservations.filter(created_at__date__lte=date_to)
        context = {
            **self.admin_site.each_context(request),
            "title": "Reservation Approval Management",
            "topbar": True,
            "opts": self.model._meta,
            "reservations": reservations,
            "flights": Flight.objects.with_route().order_by("code"),
            "statuses": Reservation.Status.choices,
            "stats": self.status_totals(),
            "selected_status": status,
            "selected_flight": flight_id,
            "date_from": date_from,
            "date_to": date_to,
        }
        return TemplateResponse(
            request, "admin/bookings/reservation/approval.html", context
        )

    def status_totals(self):
        totals = dict.fromkeys(Reservation.Status.values, 0)
        totals.update(
            Reservation.objects.order_by()
            .values_list("status")
            .annotate(total=Count("pk"))
        )
        return totals

    def approve_view(self, request, pk):
        reservation = get_object_or_404(Reservation.objects.with_flight(), pk=pk)
        if ReservationDecisionService().approve(reservation):
            messages.success(
                request,
                "Reservation for %s has been approved successfully."
                % reservation.full_name,
            )
        else:
            messages.error(request, "This reservation cannot be approved.")
        return redirect("admin:bookings_reservation_approval")

    def reject_view(self, request, pk):
        reservation = get_object_or_404(Reservation.objects.with_flight(), pk=pk)
        if ReservationDecisionService().reject(reservation):
            messages.success(
                request,
                "Reservation for %s has been rejected." % reservation.full_name,
            )
        else:
            messages.error(request, "This reservation cannot be rejected.")
        return redirect("admin:bookings_reservation_approval")
