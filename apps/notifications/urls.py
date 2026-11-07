from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path(
        "<int:pk>/read/",
        views.MarkNotificationReadView.as_view(),
        name="mark-read",
    ),
]
