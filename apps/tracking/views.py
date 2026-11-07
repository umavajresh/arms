from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from apps.core.mixins import PageMixin, public_view
from apps.flights.models import Flight

from .providers import LiveFlightLookup
from .schedule import schedule_tracking_data


@public_view
class FlightTrackerView(PageMixin, TemplateView):
    template_name = "tracking/tracker.html"
    page_title = "Live Flight Tracker"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        context["tracked_code"] = self.request.GET.get("flight", "").strip()
        context["recent_flights"] = (
            Flight.objects.unarchived()
            .with_route()
            .filter(
                estimated_arrival__gte=now - timedelta(days=1),
                departure__lte=now + timedelta(days=7),
            )
            .order_by("departure")[:8]
        )
        return context


@public_view
class FlightTrackingApiView(View):
    lookup_class = LiveFlightLookup

    def get(self, request, *args, **kwargs):
        code = request.GET.get("flight", "").strip()
        if not code:
            return JsonResponse({"error": "Enter a flight code to track."}, status=400)
        live = self.lookup_class().find(code)
        if live:
            return JsonResponse({"flight": live})
        flight = Flight.objects.unarchived().with_route().filter(code__iexact=code)
        flight = flight.first()
        if flight is None:
            return JsonResponse(
                {"error": "No active flight was found with that code."}, status=404
            )
        return JsonResponse({"flight": schedule_tracking_data(flight)})
