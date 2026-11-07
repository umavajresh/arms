import apps.accounts.managers
import django.contrib.auth.validators
import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="User",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("password", models.CharField(max_length=128, verbose_name="password")),
                (
                    "last_login",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="last login"
                    ),
                ),
                (
                    "is_superuser",
                    models.BooleanField(
                        default=False,
                        help_text="Designates that this user has all permissions without explicitly assigning them.",
                        verbose_name="superuser status",
                    ),
                ),
                (
                    "username",
                    models.CharField(
                        error_messages={
                            "unique": "A user with that username already exists."
                        },
                        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.",
                        max_length=150,
                        unique=True,
                        validators=[
                            django.contrib.auth.validators.UnicodeUsernameValidator()
                        ],
                        verbose_name="username",
                    ),
                ),
                (
                    "first_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="first name"
                    ),
                ),
                (
                    "last_name",
                    models.CharField(
                        blank=True, max_length=150, verbose_name="last name"
                    ),
                ),
                (
                    "email",
                    models.EmailField(
                        blank=True, max_length=254, verbose_name="email address"
                    ),
                ),
                (
                    "is_staff",
                    models.BooleanField(
                        default=False,
                        help_text="Designates whether the user can log into this admin site.",
                        verbose_name="staff status",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Designates whether this user should be treated as active. Unselect this instead of deleting accounts.",
                        verbose_name="active",
                    ),
                ),
                (
                    "date_joined",
                    models.DateTimeField(
                        default=django.utils.timezone.now, verbose_name="date joined"
                    ),
                ),
                (
                    "member_id",
                    models.CharField(
                        blank=True,
                        max_length=50,
                        null=True,
                        unique=True,
                        verbose_name="User ID",
                    ),
                ),
                ("mobile", models.CharField(blank=True, max_length=20)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("administrator", "Administrator"),
                            ("passenger", "Passenger"),
                        ],
                        default="passenger",
                        max_length=20,
                    ),
                ),
                ("date_of_birth", models.DateField(blank=True, null=True)),
                (
                    "security_question",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("nickname", "What is your nickname?"),
                            ("pet", "What is your pet's name?"),
                            ("birthplace", "What is your place of birth?"),
                            ("mother_maiden", "What is your mother's maiden name?"),
                            ("first_school", "What was the name of your first school?"),
                            ("first_car", "What was your first car?"),
                            (
                                "childhood_friend",
                                "What is the name of your childhood best friend?",
                            ),
                        ],
                        max_length=50,
                    ),
                ),
                ("security_answer", models.CharField(blank=True, max_length=128)),
                ("two_factor_enabled", models.BooleanField(default=False)),
                ("otp_digest", models.CharField(blank=True, max_length=128)),
                ("otp_expires_at", models.DateTimeField(blank=True, null=True)),
                (
                    "groups",
                    models.ManyToManyField(
                        blank=True,
                        help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.group",
                        verbose_name="groups",
                    ),
                ),
                (
                    "user_permissions",
                    models.ManyToManyField(
                        blank=True,
                        help_text="Specific permissions for this user.",
                        related_name="user_set",
                        related_query_name="user",
                        to="auth.permission",
                        verbose_name="user permissions",
                    ),
                ),
            ],
            options={
                "verbose_name": "user",
                "verbose_name_plural": "users",
                "abstract": False,
            },
            managers=[
                ("objects", apps.accounts.managers.UserManager()),
            ],
        ),
        migrations.CreateModel(
            name="TravelPreference",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "preferred_language",
                    models.CharField(
                        choices=[
                            ("en", "English (EN)"),
                            ("es", "Spanish (Español)"),
                            ("fr", "French (Français)"),
                            ("de", "German (Deutsch)"),
                            ("ja", "Japanese (日本語)"),
                            ("hi", "Hindi (हिन्दी)"),
                        ],
                        default="en",
                        max_length=10,
                    ),
                ),
                (
                    "preferred_currency",
                    models.CharField(
                        choices=[
                            ("USD", "USD ($)"),
                            ("EUR", "EUR (€)"),
                            ("GBP", "GBP (£)"),
                            ("JPY", "JPY (¥)"),
                            ("INR", "INR (₹)"),
                        ],
                        default="USD",
                        max_length=10,
                    ),
                ),
                (
                    "preferred_seat_class",
                    models.CharField(
                        choices=[
                            ("Economy", "Economy"),
                            ("Business", "Business Class"),
                        ],
                        default="Economy",
                        max_length=20,
                    ),
                ),
                ("dietary_preference", models.CharField(blank=True, max_length=50)),
                ("interests", models.CharField(blank=True, max_length=255)),
                (
                    "budget_level",
                    models.CharField(
                        choices=[
                            ("economy", "Budget / Economy"),
                            ("moderate", "Moderate"),
                            ("luxury", "Luxury"),
                        ],
                        default="moderate",
                        max_length=20,
                    ),
                ),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="travel_preference",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
    ]
