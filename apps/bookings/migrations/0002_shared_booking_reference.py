from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="reservation",
            name="booking_reference",
            field=models.CharField(db_index=True, editable=False, max_length=32),
        ),
    ]
