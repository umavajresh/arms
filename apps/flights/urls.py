from django.urls import path

from . import views

app_name = "flights"

urlpatterns = [
    path("search/", views.FlightSearchView.as_view(), name="search"),
    path("results/", views.FlightResultsView.as_view(), name="results"),
    path("upcoming/", views.UpcomingFlightsView.as_view(), name="upcoming"),
]
