from django import forms

from .models import Airport


class FlightSearchForm(forms.Form):
    from_airport = forms.ModelChoiceField(queryset=Airport.objects.unarchived())
    to_airport = forms.ModelChoiceField(queryset=Airport.objects.unarchived())
    departure_date = forms.DateField()


class UpcomingFlightsFilterForm(forms.Form):
    days = forms.IntegerField(min_value=1, max_value=30, required=False)
    airline = forms.IntegerField(min_value=1, required=False)
    from_airport = forms.CharField(max_length=5, required=False)
    to_airport = forms.CharField(max_length=5, required=False)
    date = forms.DateField(required=False)
