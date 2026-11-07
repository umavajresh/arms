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
    return "; ".join(
        "[%s] %s" % (field, error)
        for field, errors in form.errors.items()
        for error in errors
    )
