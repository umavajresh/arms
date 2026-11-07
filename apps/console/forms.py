from django import forms

from apps.flights.models import Aircraft, Airline, Airport, Flight
from apps.flights.services.logos import fit_logo

ACTIVE_CHOICES = ((True, "Active"), (False, "Inactive"))


class ActiveStatusField(forms.TypedChoiceField):
    def __init__(self, **kwargs):
        super().__init__(
            choices=ACTIVE_CHOICES,
            coerce=lambda value: value in (True, "True", "true", "1"),
            **kwargs,
        )


class ReferenceDataForm(forms.ModelForm):
    is_active = ActiveStatusField(label="Status")
    is_archived = forms.BooleanField(
        disabled=True, required=False, widget=forms.HiddenInput
    )


class AirlineForm(ReferenceDataForm):

    class Meta:
        model = Airline
        fields = ("code", "name", "country", "is_active", "is_archived", "logo")

    def save(self, commit=True):
        airline = super().save(commit=commit)
        if commit:
            fit_logo(airline.logo)
        return airline


class AirportForm(ReferenceDataForm):

    class Meta:
        model = Airport
        fields = ("code", "name", "city", "country", "is_active", "is_archived")


class AircraftForm(ReferenceDataForm):

    class Meta:
        model = Aircraft
        fields = (
            "code",
            "model_name",
            "manufacturer",
            "business_capacity",
            "economy_capacity",
            "is_active",
            "is_archived",
        )


class FlightForm(forms.ModelForm):
    class Meta:
        model = Flight
        fields = (
            "code",
            "airline",
            "from_airport",
            "to_airport",
            "aircraft",
            "departure",
            "estimated_arrival",
            "business_class_price",
            "economy_price",
            "currency",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["airline"].queryset = Airline.objects.available()
        self.fields["from_airport"].queryset = Airport.objects.available()
        self.fields["to_airport"].queryset = Airport.objects.available()
        self.fields["aircraft"].queryset = Aircraft.objects.available()
        self.fields["aircraft"].required = True
        self.fields["currency"].required = False

    def clean_currency(self):
        return (self.cleaned_data.get("currency") or "INR").upper()

    def clean_code(self):
        code = self.cleaned_data["code"]
        duplicates = Flight.objects.unarchived().filter(code=code)
        if duplicates.exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Flight Code already exists")
        return code
