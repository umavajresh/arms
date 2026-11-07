from django.core.management.base import BaseCommand

from apps.flights.seeding import ReferenceDataImporter


class Command(BaseCommand):
    help = "Import the bundled airline, airport, aircraft, and flight seed data."

    def handle(self, *args, **options):
        created = ReferenceDataImporter().run()
        for label, count in created.items():
            self.stdout.write("Imported %d new %s" % (count, label))
        self.stdout.write(self.style.SUCCESS("Data import completed successfully."))
