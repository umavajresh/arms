from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView, TemplateView

from apps.bookings.models import Reservation
from apps.bookings.selectors import with_seat_availability
from apps.bookings.services import ReservationDecisionService
from apps.core.http import json_failure, json_success
from apps.flights.models import Aircraft, Airline, Airport, Flight

from .forms import AircraftForm, AirlineForm, AirportForm, FlightForm
from .mixins import ArchiveView, ConsoleMixin, ModalCreateView, ModalUpdateView


class DashboardView(ConsoleMixin, TemplateView):
    template_name = "console/dashboard.html"
    page_title = "Home"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["airlines"] = Airline.objects.available().count()
        context["airport"] = Airport.objects.available().count()
        context["aircraft"] = Aircraft.objects.available().count()
        context["flight"] = Flight.objects.bookable().count()
        context["pending_reservations"] = Reservation.objects.filter(
            status=Reservation.Status.PENDING
        ).count()
        context["confirmed_reservations"] = Reservation.objects.filter(
            status=Reservation.Status.APPROVED
        ).count()
        return context


class AirlineListView(ConsoleMixin, ListView):
    template_name = "console/airline_list.html"
    page_title = "Airlines"
    context_object_name = "airlines"
    queryset = Airline.objects.unarchived()


class AirlineFormMixin:
    model = Airline
    form_class = AirlineForm
    template_name = "console/airline_form.html"
    context_object_name = "airline"
    page_title = "Manage Airline"
    created_message = "New Airline has been added successfully."
    updated_message = "Airline Details has been updated successfully."


class AirlineCreateView(AirlineFormMixin, ModalCreateView):
    pass


class AirlineUpdateView(AirlineFormMixin, ModalUpdateView):
    queryset = Airline.objects.unarchived()


class AirlineArchiveView(ArchiveView):
    model = Airline
    label = "Airline"


class AirportListView(ConsoleMixin, ListView):
    template_name = "console/airport_list.html"
    page_title = "Airports"
    context_object_name = "airports"
    queryset = Airport.objects.unarchived()


class AirportFormMixin:
    model = Airport
    form_class = AirportForm
    template_name = "console/airport_form.html"
    context_object_name = "airport"
    page_title = "Manage Airport"
    created_message = "New Airport has been added successfully."
    updated_message = "Airport Details has been updated successfully."


class AirportCreateView(AirportFormMixin, ModalCreateView):
    pass


class AirportUpdateView(AirportFormMixin, ModalUpdateView):
    queryset = Airport.objects.unarchived()


class AirportArchiveView(ArchiveView):
    model = Airport
    label = "Airport"


class AircraftListView(ConsoleMixin, ListView):
    template_name = "console/aircraft_list.html"
    page_title = "Aircraft List"
    context_object_name = "aircraft_list"
    queryset = Aircraft.objects.unarchived()


class AircraftFormMixin:
    model = Aircraft
    form_class = AircraftForm
    template_name = "console/aircraft_form.html"
    context_object_name = "aircraft"
    page_title = "Manage Aircraft"
    created_message = "Aircraft has been added successfully."
    updated_message = "Aircraft has been updated successfully."


class AircraftCreateView(AircraftFormMixin, ModalCreateView):
    pass


class AircraftUpdateView(AircraftFormMixin, ModalUpdateView):
    queryset = Aircraft.objects.unarchived()


class AircraftArchiveView(ArchiveView):
    model = Aircraft
    label = "Aircraft"


class FlightListView(ConsoleMixin, ListView):
    template_name = "console/flight_list.html"
    page_title = "Flights"
    context_object_name = "flights"
    queryset = Flight.objects.unarchived().with_route()


class FlightFormMixin:
    model = Flight
    form_class = FlightForm
    template_name = "console/flight_form.html"
    context_object_name = "flight"
    page_title = "Manage Flight"
    created_message = "New Flight has been added successfully."
    updated_message = "Flight Details has been updated successfully."

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["airlines"] = Airline.objects.available()
        context["airports"] = Airport.objects.available()
        context["aircraft_list"] = Aircraft.objects.available()
        return context


class FlightCreateView(FlightFormMixin, ModalCreateView):
    pass


class FlightUpdateView(FlightFormMixin, ModalUpdateView):
    queryset = Flight.objects.unarchived()


class FlightDetailView(ConsoleMixin, DetailView):
    template_name = "console/flight_detail.html"
    page_title = "Flight Details"
    context_object_name = "flight"

    def get_queryset(self):
        return with_seat_availability(Flight.objects.with_route())


class FlightArchiveView(ArchiveView):
    model = Flight
    label = "Flight"


class ReservationListView(ConsoleMixin, ListView):
    template_name = "console/reservation_list.html"
    page_title = "Reservations"
    context_object_name = "reservations"

    def get_queryset(self):
        return Reservation.objects.with_flight().select_related("user")


class ReservationDetailView(ConsoleMixin, DetailView):
    template_name = "console/reservation_detail.html"
    page_title = "Reservation Details"
    context_object_name = "reservation"

    def get_queryset(self):
        return Reservation.objects.with_flight().select_related("user")


class ReservationDeleteView(ConsoleMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        deleted, _ = Reservation.objects.filter(pk=pk).delete()
        if not deleted:
            return json_failure("Reservation not found.", http_status=404)
        messages.success(request, "Reservation has been deleted successfully.")
        return json_success("Reservation deleted.")


class ReservationStatusView(ConsoleMixin, View):
    http_method_names = ["post"]
    transitions = {
        Reservation.Status.APPROVED: ReservationDecisionService.approve,
        Reservation.Status.CANCELLED: ReservationDecisionService.cancel,
    }

    def post(self, request, pk):
        transition = self.transitions.get(request.POST.get("status"))
        if transition is None:
            return json_failure("A valid reservation status is required.")
        reservation = get_object_or_404(Reservation.objects.with_flight(), pk=pk)
        if not transition(ReservationDecisionService(), reservation):
            return json_failure(
                "This reservation can no longer be updated.", http_status=409
            )
        messages.success(request, "Reservation Status has been updated successfully")
        return json_success("Reservation updated.")
