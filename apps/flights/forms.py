from django import forms

from .models import Airport
from .services.window import BookingWindow


class FlightSearchForm(forms.Form):
    from_airport = forms.ModelChoiceField(
        queryset=Airport.objects.unarchived(),
        label="Origin",
        error_messages={"required": "Choose where you are flying from."},
    )
    to_airport = forms.ModelChoiceField(
        queryset=Airport.objects.unarchived(),
        label="Destination",
        error_messages={"required": "Choose where you are flying to."},
    )
    departure_date = forms.DateField(
        label="Departure date",
        error_messages={"required": "Choose a departure date."},
    )

    def clean_departure_date(self):
        departure_date = self.cleaned_data["departure_date"]
        window = BookingWindow.current()
        if departure_date < window.earliest:
            raise forms.ValidationError("Choose today or a later date.")
        if departure_date > window.latest:
            raise forms.ValidationError(
                "Flights open %d days ahead. Choose an earlier date."
                % (window.latest - window.earliest).days
            )
        return departure_date

    def clean(self):
        cleaned = super().clean()
        origin, destination = cleaned.get("from_airport"), cleaned.get("to_airport")
        if origin and origin == destination:
            raise forms.ValidationError(
                "Origin and destination must be different airports."
            )
        return cleaned


class UpcomingFlightsFilterForm(forms.Form):
    days = forms.IntegerField(min_value=1, max_value=30, required=False)
    airline = forms.IntegerField(min_value=1, required=False)
    from_airport = forms.CharField(max_length=5, required=False)
    to_airport = forms.CharField(max_length=5, required=False)
    date = forms.DateField(required=False)
