from django.contrib import admin


class ArmsAdminSite(admin.AdminSite):
    site_header = "Airline Reservation Management System"
    site_title = "ARMS Admin"
    index_title = "ARMS Administration"
