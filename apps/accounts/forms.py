from django import forms
from django.contrib.auth import forms as auth_forms
from django.contrib.auth.hashers import make_password

from .models import TravelPreference, User
from .services.recovery import normalize_security_answer


class RegistrationForm(auth_forms.UserCreationForm):
    class Meta:
        model = User
        fields = (
            "first_name",
            "last_name",
            "email",
            "member_id",
            "mobile",
            "username",
            "date_of_birth",
            "security_question",
            "security_answer",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in self.Meta.fields:
            self.fields[name].required = True

    def clean_security_answer(self):
        return normalize_security_answer(self.cleaned_data["security_answer"])

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.PASSENGER
        user.security_answer = make_password(self.cleaned_data["security_answer"])
        if commit:
            user.save()
        return user


class ProfileForm(forms.ModelForm):
    current_password = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("first_name", "last_name", "username", "email", "member_id", "mobile")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("first_name", "last_name", "email"):
            self.fields[name].required = True

    def clean_current_password(self):
        password = self.cleaned_data["current_password"]
        if not self.instance.check_password(password):
            raise forms.ValidationError("Password is incorrect.")
        return password

    def clean_email(self):
        email = self.cleaned_data["email"]
        taken = (
            User.objects.exclude(pk=self.instance.pk)
            .filter(email__iexact=email)
            .exists()
        )
        if taken:
            raise forms.ValidationError("The %s email is already taken." % email)
        return email


class StyledPasswordChangeForm(auth_forms.PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control form-control-sm rounded-0"


class TravelPreferenceForm(forms.ModelForm):
    class Meta:
        model = TravelPreference
        fields = (
            "preferred_language",
            "preferred_currency",
            "preferred_seat_class",
            "dietary_preference",
            "interests",
            "budget_level",
        )


class RecoveryStartForm(forms.Form):
    identifier = forms.CharField(max_length=150)


class IdentityVerificationForm(forms.Form):
    date_of_birth = forms.DateField()
    security_answer = forms.CharField(max_length=255)
