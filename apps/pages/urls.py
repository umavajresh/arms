from django.urls import path

from . import views

app_name = "pages"

urlpatterns = [
    path("", views.LandingView.as_view(), name="landing"),
    path("terms/", views.TermsView.as_view(), name="terms"),
    path("privacy/", views.PrivacyView.as_view(), name="privacy"),
]
