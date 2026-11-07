from django.forms.forms import NON_FIELD_ERRORS
from django.forms.utils import pretty_name
from django.http import JsonResponse


def expects_json(request):
    return request.headers.get(
        "x-requested-with"
    ) == "XMLHttpRequest" or "application/json" in request.headers.get("accept", "")


def json_result(result, message="", http_status=200, **payload):
    return JsonResponse(
        {"status": result, "msg": message, **payload}, status=http_status
    )


def json_success(message="", **payload):
    return json_result("success", message, **payload)


def json_failure(message, http_status=400, **payload):
    return json_result("failed", message, http_status=http_status, **payload)


def format_form_errors(form):
    return " ".join(
        _sentence(_field_label(form, field), error)
        for field, errors in form.errors.items()
        for error in errors
    )


def _field_label(form, field):
    if field == NON_FIELD_ERRORS:
        return ""
    bound = form.fields.get(field)
    return str(bound.label) if bound and bound.label else pretty_name(field)


def _sentence(label, error):
    text = "%s: %s" % (label, error) if label else str(error)
    return text if text.endswith((".", "!", "?")) else text + "."
