from django.contrib.admin.apps import AdminConfig


class ArmsAdminConfig(AdminConfig):
    default_site = "config.admin.ArmsAdminSite"
