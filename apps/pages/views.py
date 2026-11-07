from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.core.mixins import PageMixin, public_view
from apps.flights.models import Airport
from apps.flights.services.window import BookingWindow


@public_view
class LandingView(PageMixin, TemplateView):
    template_name = "pages/landing.html"
    page_title = "ARMS 2.0 - Cinematic Airline Reservation and Travel Management"

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(request.user.get_dashboard_url())
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["airports"] = Airport.objects.available()
        context["booking_window"] = BookingWindow.current()
        return context


@public_view
class TermsView(PageMixin, TemplateView):
    template_name = "pages/terms.html"
    page_title = "Terms of Service"


@public_view
class PrivacyView(PageMixin, TemplateView):
    template_name = "pages/privacy.html"
    page_title = "Privacy Policy"
