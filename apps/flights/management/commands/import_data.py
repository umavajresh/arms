from django.core.management.base import BaseCommand

from apps.flights.seeding import ReferenceDataImporter


class Command(BaseCommand):
    help = (
        "Import the bundled airline, airport, aircraft, flight, and schedule "
        "seed data."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--if-empty",
            action="store_true",
            help="Only import when the database has no airlines or airports yet.",
        )

    def handle(self, *args, **options):
        importer = ReferenceDataImporter()
        if options["if_empty"] and importer.has_reference_data():
            self.stdout.write("Reference data already exists; nothing imported.")
            return
        created = importer.run()
        for label, count in created.items():
            self.stdout.write("Imported %d new %s" % (count, label))
        self.stdout.write(self.style.SUCCESS("Data import completed successfully."))
