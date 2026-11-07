from django.urls import path

from . import views

app_name = "bookings"

urlpatterns = [
    path("dashboard/", views.PassengerDashboardView.as_view(), name="dashboard"),
    path("mine/", views.MyReservationsView.as_view(), name="my-reservations"),
    path(
        "<int:pk>/cancel/",
        views.CancelReservationView.as_view(),
        name="cancel",
    ),
    path(
        "flights/<int:pk>/seats/",
        views.SeatSelectionView.as_view(),
        name="seat-selection",
    ),
    path(
        "flights/<int:pk>/passengers/",
        views.ReservationFormView.as_view(),
        name="reservation-form",
    ),
    path("human-check/", views.HumanCheckView.as_view(), name="human-check"),
    path("verify/", views.ReservationVerifyView.as_view(), name="verify"),
    path("submit/", views.ReservationSubmitView.as_view(), name="submit"),
    path(
        "confirmation/<str:reference>/",
        views.BookingConfirmationView.as_view(),
        name="confirmation",
    ),
    path("guest/", views.GuestLookupView.as_view(), name="guest-lookup"),
    path("guest/cancel/", views.GuestCancelView.as_view(), name="guest-cancel"),
]
