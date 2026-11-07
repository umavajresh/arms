from django import forms
from django.test import SimpleTestCase

from apps.core.http import format_form_errors


class SampleForm(forms.Form):
    member_id = forms.CharField(label="User ID")
    mobile_number = forms.CharField()

    def clean(self):
        raise forms.ValidationError("Airline code already exists")


class FormErrorFormattingTests(SimpleTestCase):
    def test_errors_use_field_labels_and_plain_sentences(self):
        form = SampleForm(data={})
        self.assertEqual(
            format_form_errors(form),
            "User ID: This field is required. "
            "Mobile number: This field is required. "
            "Airline code already exists.",
        )
