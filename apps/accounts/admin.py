from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import TravelPreference, User


@admin.register(User)
class ArmsUserAdmin(UserAdmin):
    list_display = ("username", "member_id", "email", "role", "is_active")
    list_filter = ("role", "is_active", "is_staff", "two_factor_enabled")
    search_fields = ("username", "member_id", "email", "first_name", "last_name")
    fieldsets = UserAdmin.fieldsets + (
        (
            "ARMS profile",
            {"fields": ("member_id", "mobile", "role", "date_of_birth")},
        ),
        (
            "Security",
            {"fields": ("security_question", "two_factor_enabled")},
        ),
    )


@admin.register(TravelPreference)
class TravelPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "preferred_language", "preferred_currency", "budget_level")
    search_fields = ("user__username",)
