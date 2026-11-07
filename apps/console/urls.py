from django.urls import path

from . import views

app_name = "console"


def resource_patterns(prefix, name, list_view, create_view, update_view, archive_view):
    return [
        path("%s/" % prefix, list_view.as_view(), name="%s-list" % name),
        path("%s/new/" % prefix, create_view.as_view(), name="%s-create" % name),
        path(
            "%s/<int:pk>/edit/" % prefix,
            update_view.as_view(),
            name="%s-update" % name,
        ),
        path(
            "%s/<int:pk>/archive/" % prefix,
            archive_view.as_view(),
            name="%s-archive" % name,
        ),
    ]


urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    *resource_patterns(
        "airlines",
        "airline",
        views.AirlineListView,
        views.AirlineCreateView,
        views.AirlineUpdateView,
        views.AirlineArchiveView,
    ),
    *resource_patterns(
        "airports",
        "airport",
        views.AirportListView,
        views.AirportCreateView,
        views.AirportUpdateView,
        views.AirportArchiveView,
    ),
    *resource_patterns(
        "aircraft",
        "aircraft",
        views.AircraftListView,
        views.AircraftCreateView,
        views.AircraftUpdateView,
        views.AircraftArchiveView,
    ),
    *resource_patterns(
        "flights",
        "flight",
        views.FlightListView,
        views.FlightCreateView,
        views.FlightUpdateView,
        views.FlightArchiveView,
    ),
    path("flights/<int:pk>/", views.FlightDetailView.as_view(), name="flight-detail"),
    path(
        "reservations/",
        views.ReservationListView.as_view(),
        name="reservation-list",
    ),
    path(
        "reservations/<int:pk>/",
        views.ReservationDetailView.as_view(),
        name="reservation-detail",
    ),
    path(
        "reservations/<int:pk>/delete/",
        views.ReservationDeleteView.as_view(),
        name="reservation-delete",
    ),
    path(
        "reservations/<int:pk>/status/",
        views.ReservationStatusView.as_view(),
        name="reservation-status",
    ),
]
