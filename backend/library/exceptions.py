from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class Conflict(APIException):
    """409 — конфликт состояния (занятый экземпляр, недопустимый переход статуса)."""

    status_code = status.HTTP_409_CONFLICT
    default_detail = "Операция конфликтует с текущим состоянием объекта."
    default_code = "conflict"


def api_exception_handler(exc, context):
    """Единый формат ошибок: {"detail": "...", "errors": {поле: [сообщения]}}"""
    response = exception_handler(exc, context)
    if response is None:
        return None

    if isinstance(exc, ValidationError):
        errors = response.data
        if isinstance(errors, list):
            errors = {"non_field_errors": errors}
        response.data = {"detail": "Проверьте введённые данные.", "errors": errors}
    elif isinstance(response.data, dict) and "detail" in response.data:
        response.data = {"detail": str(response.data["detail"])}
    return response
