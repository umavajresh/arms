from django import forms

from .models import Reservation
from .services import ContactDetails, PassengerDetails


class PassengerForm(forms.Form):
    first_name = forms.CharField(max_length=250)
    middle_name = forms.CharField(max_length=250, required=False)
    last_name = forms.CharField(max_length=250)
    gender = forms.ChoiceField(choices=Reservation.Gender.choices)

    def to_details(self):
        return PassengerDetails(**self.cleaned_data)


class ContactForm(forms.Form):
    email = forms.EmailField(max_length=254)
    contact = forms.CharField(max_length=250)
    address = forms.CharField(widget=forms.Textarea, required=False)

    def to_details(self):
        return ContactDetails(**self.cleaned_data)


class GuestLookupForm(forms.Form):
    reference = forms.CharField(max_length=32)
    verification = forms.CharField(max_length=254)
