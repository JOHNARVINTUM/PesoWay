from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Stable public error envelope without tracebacks or internal exception details."""
    response = exception_handler(exc, context)
    if response is None:
        return Response({"error": {"code": "internal_error", "message": "An unexpected error occurred."}}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    detail = response.data
    code = getattr(exc, "default_code", "request_error")
    message = detail if isinstance(detail, str) else "Request could not be completed."
    payload = {"error": {"code": code, "message": message}}
    if isinstance(detail, dict):
        payload["error"]["details"] = detail
    response.data = payload
    return response
