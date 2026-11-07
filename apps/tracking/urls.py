from django.urls import path

from . import views

app_name = "tracking"

urlpatterns = [
    path("", views.FlightTrackerView.as_view(), name="tracker"),
    path("api/", views.FlightTrackingApiView.as_view(), name="tracker-api"),
]
