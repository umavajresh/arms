import datetime
from urllib.parse import urlencode

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone
from django.views.generic import TemplateView

from apps.bookings.selectors import with_seat_availability
from apps.core.mixins import PageMixin, PassengerAreaMixin, public_view

from .forms import FlightSearchForm, UpcomingFlightsFilterForm
from .models import Airline, Airport, Flight
from .services.provisioning import RouteProvisioner
from .services.search import FlightSearch, SearchFilters

UPCOMING_DAY_OPTIONS = (1, 3, 7, 14, 30)


@public_view
class FlightSearchView(PassengerAreaMixin, PageMixin, TemplateView):
    template_name = "flights/search.html"
    page_title = "Search Available Flight"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["airlines"] = Airline.objects.available()
        context["airports"] = Airport.objects.available()
        return context


@public_view
class FlightResultsView(PassengerAreaMixin, PageMixin, TemplateView):
    template_name = "flights/results.html"
    page_title = "Search Result"

    def get(self, request, *args, **kwargs):
        form = FlightSearchForm(request.GET)
        if not form.is_valid():
            messages.error(request, "Invalid Search Inputs")
            return redirect("pages:landing")
        self.criteria = form.cleaned_data
        RouteProvisioner().ensure_departures(
            self.criteria["from_airport"],
            self.criteria["to_airport"],
            self.criteria["departure_date"],
        )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filters = SearchFilters.from_query(self.request.GET)
        outcome = FlightSearch(
            self.criteria["from_airport"],
            self.criteria["to_airport"],
            self.criteria["departure_date"],
            prepare=with_seat_availability,
        ).run(filters)
        route = {
            "from_airport": self.criteria["from_airport"].pk,
            "to_airport": self.criteria["to_airport"].pk,
            "departure_date": self.criteria["departure_date"].isoformat(),
        }
        context.update(route)
        context["route_query"] = urlencode(route)
        context["price_sort"] = filters.price_sort
        context["min_price"] = filters.min_price
        context["max_price"] = filters.max_price
        context["time_filter"] = filters.time_filter
        context["flights"] = outcome.flights
        context["nearby_flights"] = outcome.nearby_flights
        context["filter_relaxed"] = outcome.filter_relaxed
        context["unfiltered_count"] = outcome.unfiltered_count
        context["min_available_price"] = outcome.min_available_price
        context["max_available_price"] = outcome.max_available_price
        return context


@public_view
class UpcomingFlightsView(PassengerAreaMixin, PageMixin, TemplateView):
    template_name = "flights/upcoming.html"
    page_title = "Upcoming Flights"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        form = UpcomingFlightsFilterForm(self.request.GET)
        filters = form.cleaned_data if form.is_valid() else {}
        today = timezone.localdate()
        days = filters.get("days") or 3
        start = filters.get("date") or today
        end = start + datetime.timedelta(days=days)
        flights = Flight.objects.bookable().with_route()
        flights = flights.filter(departure__date__gte=start, departure__date__lte=end)
        if filters.get("airline"):
            flights = flights.filter(airline_id=filters["airline"])
        if filters.get("from_airport"):
            flights = flights.filter(from_airport__code__iexact=filters["from_airport"])
        if filters.get("to_airport"):
            flights = flights.filter(to_airport__code__iexact=filters["to_airport"])
        context["flights"] = with_seat_availability(flights.order_by("departure"))
        context["today"] = today
        context["start_date"] = start
        context["end_date"] = end
        context["days"] = days
        context["days_options"] = UPCOMING_DAY_OPTIONS
        context["airlines"] = Airline.objects.available()
        context["airports"] = Airport.objects.available().order_by("code")
        context["selected_airline"] = str(filters.get("airline") or "")
        context["selected_from_airport"] = filters.get("from_airport", "")
        context["selected_to_airport"] = filters.get("to_airport", "")
        context["selected_date"] = start.isoformat()
        return context
