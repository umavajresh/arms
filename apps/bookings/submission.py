from apps.core.http import format_form_errors

from .forms import ContactForm, PassengerForm
from .services import ReservationRejected


class ReservationSubmission:
    def __init__(self, data, selection):
        self.data = data
        self.selection = selection

    def parse(self):
        if self.data.get("passenger_count") != str(self.selection.passenger_count):
            raise ReservationRejected("Please select seats for all passengers again.")
        passengers = [
            self._passenger(index, seat)
            for index, seat in enumerate(self.selection.seats)
        ]
        return passengers, self._contact()

    def _passenger(self, index, seat):
        prefix = "passenger_%d" % index
        if (
            self.data.get("%s_seat" % prefix) != seat.code
            or self.data.get("%s_class" % prefix) != seat.cabin
        ):
            raise ReservationRejected(
                "The passenger seat selection has changed. Please start again."
            )
        form = PassengerForm(data=self.data, prefix=prefix)
        if not form.is_valid():
            raise ReservationRejected(
                "Please enter valid details for Passenger %d. %s"
                % (index + 1, format_form_errors(form))
            )
        return form.to_details()

    def _contact(self):
        form = ContactForm(data=self.data)
        if not form.is_valid():
            raise ReservationRejected(format_form_errors(form))
        return form.to_details()
