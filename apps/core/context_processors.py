SITE_NAME = "ARMS 2.0"
SITE_FULL_NAME = "AI-Powered Airline Reservation & Travel Management System"


def branding(request):
    return {"system_name": SITE_NAME, "system_full_name": SITE_FULL_NAME}
