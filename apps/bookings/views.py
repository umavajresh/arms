from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views import View
from django.views.generic import ListView, TemplateView

from apps.core.http import json_failure, json_success
from apps.core.mixins import PageMixin, PassengerAreaMixin, public_view
from apps.core.rate_limit import RateLimiter
from apps.flights.models import Flight
from apps.notifications.models import Notification

from .forms import GuestLookupForm
from .guest_access import (
    GuestAccess,
    find_guest_reservation,
    is_valid_guest_request,
    normalize_reference,
    normalize_verifier,
)
from .models import Reservation
from .seating import SeatMap
from .selection import SeatSelectionError, SeatSelectionStore, parse_seat_request
from .selectors import with_seat_availability
from .services import ReservationRejected, ReservationService
from .submission import ReservationSubmission
from .verification import ReservationVerifier, VerificationFailed, VerificationLocked

guest_lookup_limiter = RateLimiter("guest-lookup", limit=5, window_seconds=600)
guest_cancel_limiter = RateLimiter("guest-cancel", limit=5, window_seconds=600)


class BookableFlightMixin:
    def dispatch(self, request, *args, **kwargs):
        self.flight = get_object_or_404(
            with_seat_availability(Flight.objects.unarchived().with_route()),
            pk=kwargs["pk"],
        )
        if not self.flight.is_bookable:
            messages.error(
                request,
                "This flight has already departed. You cannot book a past flight.",
            )
            return redirect("flights:search")
        self.seat_map = SeatMap(self.flight)
        return super().dispatch(request, *args, **kwargs)


@public_view
class SeatSelectionView(
    PassengerAreaMixin, BookableFlightMixin, PageMixin, TemplateView
):
    template_name = "bookings/seat_selection.html"
    page_title = "Select Your Seat"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        occupied = Reservation.objects.occupied_seat_numbers(self.flight)
        context["flight"] = self.flight
        context["business_seats"] = self.seat_map.availability(
            Reservation.Cabin.BUSINESS, occupied
        )
        context["economy_seats"] = self.seat_map.availability(
            Reservation.Cabin.ECONOMY, occupied
        )
        return context

    def post(self, request, *args, **kwargs):
        try:
            selection = parse_seat_request(
                request.POST.get("selected_seats"),
                self.seat_map,
                Reservation.objects.occupied_seat_numbers(self.flight),
            )
        except SeatSelectionError as error:
            messages.error(request, str(error))
            return self.get(request, *args, **kwargs)
        SeatSelectionStore(request.session).save(selection)
        return redirect("bookings:reservation-form", pk=self.flight.pk)


@public_view
class ReservationFormView(
    PassengerAreaMixin, BookableFlightMixin, PageMixin, TemplateView
):
    template_name = "bookings/reservation_form.html"
    page_title = "Passenger Details"

    def get(self, request, *args, **kwargs):
        self.selection = SeatSelectionStore(request.session).load(self.seat_map)
        if self.selection is None:
            messages.warning(request, "Please select seats first")
            return redirect("bookings:seat-selection", pk=self.flight.pk)
        occupied = Reservation.objects.occupied_seat_numbers(self.flight)
        if occupied & self.selection.seat_codes:
            messages.error(
                request, "A selected seat is invalid or no longer available."
            )
            return redirect("bookings:seat-selection", pk=self.flight.pk)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        seats = [
            {
                "seat": seat.code,
                "class": seat.cabin,
                "display_class": seat.cabin_label,
                "price": float(self.seat_map.fare_for(seat)),
            }
            for seat in self.selection.seats
        ]
        context["flight"] = self.flight
        context["is_guest"] = not self.request.user.is_authenticated
        context["passenger_count"] = self.selection.passenger_count
        context["selected_seats"] = seats
        context["total_price"] = sum(seat["price"] for seat in seats)
        context["reservation_payload"] = {
            "passenger_count": self.selection.passenger_count,
            "selected_seats": seats,
        }
        return context


class HumanCheckView(TemplateView):
    template_name = "bookings/partials/human_check.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        first, second = ReservationVerifier(self.request.session).issue_check()
        context["first"] = first
        context["second"] = second
        return context


class ReservationVerifyView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        try:
            ReservationVerifier(request.session).verify(
                request.user,
                request.POST.get("password"),
                request.POST.get("check_answer"),
            )
        except VerificationLocked:
            return json_failure(
                "Too many attempts. Please wait before trying again.",
                http_status=429,
            )
        except VerificationFailed as error:
            return json_failure(str(error))
        return json_success("Verification successful.")


@public_view
class ReservationSubmitView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        is_guest = not request.user.is_authenticated
        if is_guest and request.POST.get("is_guest") != "1":
            return json_failure(
                "Please sign in before submitting a reservation.", http_status=401
            )
        verifier = ReservationVerifier(request.session)
        if not is_guest and not verifier.is_verified():
            return json_failure(
                "Please complete password and security verification again.",
                http_status=403,
            )
        store = SeatSelectionStore(request.session)
        selection = self.load_selection(store)
        if selection is None:
            return json_failure("Please select seats for this flight again.")
        try:
            passengers, contact = ReservationSubmission(request.POST, selection).parse()
            reservations = ReservationService().submit(
                selection, passengers, contact, user=None if is_guest else request.user
            )
        except ReservationRejected as error:
            return json_failure(error.message, http_status=error.http_status)
        store.clear()
        verifier.consume()
        return self.success_response(reservations, is_guest)

    def load_selection(self, store):
        flight_id = self.request.POST.get("flight", "")
        if not flight_id.isdecimal():
            return None
        flight = Flight.objects.unarchived().filter(pk=flight_id).first()
        return store.load(SeatMap(flight)) if flight else None

    def success_response(self, reservations, is_guest):
        reference = reservations[0].booking_reference
        if is_guest:
            GuestAccess(self.request.session).remember_new_booking(reference)
            redirect_url = reverse("bookings:confirmation", args=[reference])
        else:
            redirect_url = reverse("bookings:my-reservations")
        if len(reservations) == 1:
            message = (
                "Your reservation has been submitted successfully. "
                "It is now pending admin approval."
            )
        else:
            message = (
                "Your reservation for %d passengers has been submitted "
                "successfully. It is now pending admin approval." % len(reservations)
            )
        messages.success(self.request, message)
        return json_success(
            message,
            booking_reference=reference,
            is_guest=is_guest,
            redirect=redirect_url,
        )


@public_view
class BookingConfirmationView(PageMixin, TemplateView):
    template_name = "bookings/confirmation.html"

    def dispatch(self, request, *args, **kwargs):
        self.reference = normalize_reference(kwargs["reference"])
        reservations = Reservation.objects.with_flight().filter(
            booking_reference=self.reference
        )
        if not GuestAccess(request.session).allows(self.reference):
            if not request.user.is_authenticated:
                messages.error(
                    request,
                    "Verify your passenger details through Guest Booking Lookup "
                    "before viewing reservation details.",
                )
                return redirect("bookings:guest-lookup")
            reservations = reservations.filter(user=request.user)
        self.reservations = list(reservations)
        if not self.reservations:
            messages.error(request, "Reservation reference not found.")
            return redirect("bookings:guest-lookup")
        return super().dispatch(request, *args, **kwargs)

    def get_page_title(self):
        return "Reservation Confirmation - %s" % self.reference

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["reservation"] = self.reservations[0]
        context["all_passengers"] = self.reservations
        context["is_guest"] = self.reservations[0].is_guest
        return context


@public_view
class GuestLookupView(PageMixin, TemplateView):
    template_name = "bookings/guest_lookup.html"
    page_title = "Guest Reservation Lookup"

    def post(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        if guest_lookup_limiter.is_limited(request):
            messages.error(
                request,
                "Too many lookup attempts. Please wait 10 minutes before trying again.",
            )
            return self.render_to_response(context)
        form = GuestLookupForm(request.POST)
        reference = normalize_reference(form.data.get("reference"))
        verifier = normalize_verifier(form.data.get("verification"))
        if not form.is_valid() or not is_valid_guest_request(reference, verifier):
            messages.error(
                request,
                "Please enter both the booking reference and passenger email "
                "or last name.",
            )
            return self.render_to_response(context)
        reservation = find_guest_reservation(reference, verifier)
        if reservation is None:
            messages.error(
                request,
                "No reservation found matching the provided reference "
                "and passenger verification.",
            )
            return self.render_to_response(context)
        GuestAccess(request.session).grant(reference)
        context["found_reservation"] = reservation
        context["can_cancel"] = reservation.can_cancel
        return self.render_to_response(context)


@public_view
class GuestCancelView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        if guest_cancel_limiter.is_limited(request):
            return json_failure(
                "Too many cancellation attempts. "
                "Please wait 10 minutes before trying again.",
                http_status=429,
            )
        reference = normalize_reference(request.POST.get("reference"))
        verifier = normalize_verifier(request.POST.get("verification"))
        if not is_valid_guest_request(reference, verifier):
            return json_failure("Missing required verification details.")
        if not Reservation.objects.filter(booking_reference=reference).exists():
            return json_failure("Reservation not found.", http_status=404)
        reservation = find_guest_reservation(reference, verifier)
        if reservation is None:
            return json_failure(
                "Verification failed. Passenger details do not match.",
                http_status=403,
            )
        try:
            ReservationService().cancel(reservation)
        except ReservationRejected as error:
            return json_failure(error.message)
        messages.success(
            request, "Reservation %s has been successfully cancelled." % reference
        )
        return json_success("Reservation successfully cancelled.")


class PassengerDashboardView(PassengerAreaMixin, PageMixin, TemplateView):
    template_name = "bookings/dashboard.html"
    page_title = "User Dashboard"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        context["recent_reservations"] = Reservation.objects.with_flight().filter(
            user=user
        )[:3]
        context["notifications"] = Notification.objects.unread().filter(user=user)
        return context


class MyReservationsView(PassengerAreaMixin, PageMixin, ListView):
    template_name = "bookings/my_reservations.html"
    page_title = "My Reservations"
    context_object_name = "reservations"

    def get_queryset(self):
        return Reservation.objects.with_flight().filter(user=self.request.user)


class CancelReservationView(PassengerAreaMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        reservation = (
            Reservation.objects.with_flight().filter(pk=pk, user=request.user).first()
        )
        if reservation is None:
            return json_failure(
                "Reservation not found or unavailable.", http_status=404
            )
        try:
            ReservationService().cancel(reservation)
        except ReservationRejected as error:
            return json_failure(error.message, http_status=error.http_status)
        return json_success("Reservation successfully cancelled.")
