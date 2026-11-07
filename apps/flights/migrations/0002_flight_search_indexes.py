from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("flights", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="flight",
            index=models.Index(
                fields=["from_airport", "to_airport", "departure"],
                name="flight_route_departure_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="flight",
            index=models.Index(fields=["departure"], name="flight_departure_idx"),
        ),
    ]
