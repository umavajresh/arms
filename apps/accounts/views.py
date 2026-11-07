from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth import views as auth_views
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.messages.views import SuccessMessageMixin
from django.shortcuts import redirect
from django.urls import reverse, reverse_lazy
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import FormView, TemplateView, UpdateView

from apps.core.http import (
    expects_json,
    format_form_errors,
    json_failure,
    json_result,
    json_success,
)
from apps.core.mixins import PageMixin, public_view

from .forms import (
    IdentityVerificationForm,
    ProfileForm,
    RecoveryStartForm,
    RegistrationForm,
    StyledPasswordChangeForm,
    TravelPreferenceForm,
)
from .models import TravelPreference
from .services.recovery import PasswordRecoveryFlow
from .services.two_factor import TwoFactorChallenge


class AnonymousOnlyMixin:
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(request.user.get_dashboard_url())
        return super().dispatch(request, *args, **kwargs)


class AuthPageMixin(PageMixin):
    topbar = False
    footer = False


@public_view
class LoginView(AnonymousOnlyMixin, AuthPageMixin, TemplateView):
    template_name = "accounts/login.html"
    page_title = "Login"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["next"] = self.request.GET.get("next", "")
        return context

    def post(self, request, *args, **kwargs):
        identifier = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""
        if not identifier or not password:
            return json_failure("Enter your User ID or username and password")
        user = authenticate(request, username=identifier, password=password)
        if user is None:
            return json_failure("Incorrect User ID or password")
        if user.two_factor_enabled:
            TwoFactorChallenge(request.session).start(user)
            return json_result(
                "2fa_required", redirect=reverse("accounts:two-factor-verify")
            )
        login(request, user)
        return json_success(redirect=self.get_success_url(user))

    def get_success_url(self, user):
        next_url = self.request.POST.get("next", "")
        is_safe = url_has_allowed_host_and_scheme(
            next_url,
            allowed_hosts={self.request.get_host()},
            require_https=self.request.is_secure(),
        )
        return next_url if next_url and is_safe else user.get_dashboard_url()


class LogoutView(auth_views.LogoutView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        messages.success(request, "You have been logged out successfully")
        return response


@public_view
class RegistrationView(AnonymousOnlyMixin, AuthPageMixin, FormView):
    template_name = "accounts/register.html"
    page_title = "User Registration"
    form_class = RegistrationForm

    def form_valid(self, form):
        form.save()
        messages.success(self.request, "Your Account has been created successfully")
        return json_success("Registration successful! Redirecting to login page.")

    def form_invalid(self, form):
        return json_failure(
            format_form_errors(form)
            or "Form validation failed. Please check all fields and try again."
        )


@public_view
class TwoFactorVerifyView(AnonymousOnlyMixin, AuthPageMixin, TemplateView):
    template_name = "accounts/two_factor_verify.html"
    page_title = "Two-Factor Verification"

    def dispatch(self, request, *args, **kwargs):
        self.challenge = TwoFactorChallenge(request.session)
        self.pending_user = self.challenge.pending_user()
        if not request.user.is_authenticated and self.pending_user is None:
            self.challenge.clear()
            messages.error(
                request,
                "Your two-factor verification session has expired. "
                "Please sign in again.",
            )
            return redirect("accounts:login")
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["verify_username"] = self.pending_user.username
        context["masked_email"] = self.pending_user.masked_email
        return context

    def post(self, request, *args, **kwargs):
        if self.challenge.attempts_exhausted():
            self.challenge.clear()
            messages.error(
                request, "Too many failed verification attempts. Please sign in again."
            )
            return redirect("accounts:login")
        code = (request.POST.get("otp_code") or "").strip()
        if not code:
            messages.error(request, "Please enter the 6-digit verification code.")
            return self.get(request, *args, **kwargs)
        if not self.challenge.verify(self.pending_user, code):
            messages.error(
                request,
                "Invalid or expired verification code. Please check and try again.",
            )
            return self.get(request, *args, **kwargs)
        self.challenge.clear()
        login(request, self.pending_user)
        messages.success(
            request,
            "Welcome back, %s. Two-factor authentication verified."
            % (self.pending_user.first_name or self.pending_user.username),
        )
        return redirect(self.pending_user.get_dashboard_url())


@public_view
class TwoFactorResendView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        challenge = TwoFactorChallenge(request.session)
        user = challenge.pending_user()
        if user is None:
            challenge.clear()
            messages.error(request, "Your two-factor verification session has expired.")
            return redirect("accounts:login")
        if challenge.send_code(user):
            messages.info(request, "A new 6-digit verification code has been sent.")
        else:
            messages.error(request, "The verification code could not be delivered.")
        return redirect("accounts:two-factor-verify")


class TwoFactorToggleView(View):
    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        user = request.user
        user.two_factor_enabled = not user.two_factor_enabled
        user.save(update_fields=["two_factor_enabled"])
        state = "enabled" if user.two_factor_enabled else "disabled"
        messages.success(
            request, "Two-factor authentication has been %s for your account." % state
        )
        return redirect("accounts:profile")


class ProfileView(PageMixin, TemplateView):
    template_name = "accounts/profile.html"
    page_title = "Profile"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        preference, _ = TravelPreference.objects.get_or_create(user=self.request.user)
        context["preference_form"] = TravelPreferenceForm(instance=preference)
        return context


class ProfileUpdateView(PageMixin, SuccessMessageMixin, UpdateView):
    template_name = "accounts/profile_form.html"
    page_title = "Update Profile"
    form_class = ProfileForm
    success_url = reverse_lazy("accounts:profile")
    success_message = "Profile has been updated"

    def get_object(self, queryset=None):
        return self.request.user


class PasswordChangeView(PageMixin, SuccessMessageMixin, auth_views.PasswordChangeView):
    template_name = "accounts/password_change.html"
    page_title = "Update Password"
    form_class = StyledPasswordChangeForm
    success_url = reverse_lazy("accounts:profile")
    success_message = "Your Account Password has been updated successfully"


class TravelPreferenceUpdateView(SuccessMessageMixin, UpdateView):
    http_method_names = ["post"]
    form_class = TravelPreferenceForm
    success_url = reverse_lazy("accounts:profile")
    success_message = "Your travel preferences have been updated."

    def get_object(self, queryset=None):
        preference, _ = TravelPreference.objects.get_or_create(user=self.request.user)
        return preference

    def form_invalid(self, form):
        messages.error(self.request, format_form_errors(form))
        return redirect(self.success_url)


@public_view
class RecoveryStartView(AuthPageMixin, FormView):
    template_name = "accounts/recovery_start.html"
    page_title = "Forgot Password"
    form_class = RecoveryStartForm

    def form_valid(self, form):
        PasswordRecoveryFlow(self.request.session).begin(
            form.cleaned_data["identifier"].strip()
        )
        messages.info(
            self.request,
            "If the account can be verified, you can continue with password recovery.",
        )
        return redirect("accounts:recovery-verify")


class RecoveryStepMixin(AuthPageMixin):
    expired_message = "Session expired. Please restart the password reset process."

    def dispatch(self, request, *args, **kwargs):
        self.flow = PasswordRecoveryFlow(request.session)
        if not self.flow_is_ready():
            messages.error(request, self.expired_message)
            return redirect("accounts:recovery-start")
        return super().dispatch(request, *args, **kwargs)

    def flow_is_ready(self):
        return self.flow.is_active()


@public_view
class RecoveryVerifyView(RecoveryStepMixin, FormView):
    template_name = "accounts/recovery_verify.html"
    page_title = "Verify Identity"
    form_class = IdentityVerificationForm

    def form_valid(self, form):
        if self.flow.verify_identity(
            form.cleaned_data["date_of_birth"], form.cleaned_data["security_answer"]
        ):
            return redirect("accounts:recovery-reset")
        return self.reject()

    def form_invalid(self, form):
        self.flow.verify_identity(None, "")
        return self.reject()

    def reject(self):
        if not self.flow.is_active():
            messages.error(
                self.request, "Too many attempts. Please restart password recovery."
            )
            return redirect("accounts:recovery-start")
        messages.error(self.request, "The details did not match. Please try again.")
        return self.render_to_response(self.get_context_data())


@public_view
class RecoveryResetView(RecoveryStepMixin, FormView):
    template_name = "accounts/recovery_reset.html"
    page_title = "Reset Password"
    form_class = SetPasswordForm
    expired_message = "Please verify your identity first."

    def flow_is_ready(self):
        self.recovering_user = self.flow.user() if self.flow.is_verified() else None
        if self.recovering_user is None:
            self.flow.clear()
        return self.recovering_user is not None

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.recovering_user
        return kwargs

    def form_valid(self, form):
        form.save()
        self.flow.clear()
        message = (
            "Password has been reset successfully. "
            "You can now login with your new password."
        )
        if expects_json(self.request):
            return json_success(message)
        messages.success(self.request, message)
        return redirect("accounts:login")

    def form_invalid(self, form):
        message = " ".join(error for errors in form.errors.values() for error in errors)
        if expects_json(self.request):
            return json_failure(message)
        messages.error(self.request, message)
        return super().form_invalid(form)
