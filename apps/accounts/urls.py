from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("register/", views.RegistrationView.as_view(), name="register"),
    path("two-factor/", views.TwoFactorVerifyView.as_view(), name="two-factor-verify"),
    path(
        "two-factor/resend/",
        views.TwoFactorResendView.as_view(),
        name="two-factor-resend",
    ),
    path(
        "two-factor/toggle/",
        views.TwoFactorToggleView.as_view(),
        name="two-factor-toggle",
    ),
    path("profile/", views.ProfileView.as_view(), name="profile"),
    path("profile/edit/", views.ProfileUpdateView.as_view(), name="profile-edit"),
    path(
        "profile/password/",
        views.PasswordChangeView.as_view(),
        name="password-change",
    ),
    path(
        "profile/preferences/",
        views.TravelPreferenceUpdateView.as_view(),
        name="preferences-update",
    ),
    path("recovery/", views.RecoveryStartView.as_view(), name="recovery-start"),
    path(
        "recovery/verify/", views.RecoveryVerifyView.as_view(), name="recovery-verify"
    ),
    path("recovery/reset/", views.RecoveryResetView.as_view(), name="recovery-reset"),
]
