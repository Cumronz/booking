"""Бизнес-правила обмена книгами. Все переходы статусов проходят только здесь."""
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from .exceptions import Conflict
from .models import LOAN_TRANSITIONS, Copy, Loan


def _fresh(loan_id):
    return Loan.objects.select_related("copy__book", "copy__owner", "borrower").get(pk=loan_id)


def _load_locked(loan_id, user):
    """Блокирует экземпляр, затем запрос (всегда в таком порядке — без дедлоков).

    Посторонний пользователь получает 404, чтобы не раскрывать чужие запросы.
    """
    copy_id = Loan.objects.filter(pk=loan_id).values_list("copy_id", flat=True).first()
    if copy_id is None:
        raise NotFound("Запрос не найден.")
    copy = Copy.objects.select_for_update().get(pk=copy_id)
    loan = Loan.objects.select_for_update().get(pk=loan_id)
    loan.copy = copy
    if user.id not in (loan.borrower_id, copy.owner_id):
        raise NotFound("Запрос не найден.")
    return loan


def _require_owner(loan, user):
    if loan.copy.owner_id != user.id:
        raise PermissionDenied("Это действие доступно только владельцу экземпляра.")


def _move(loan, target):
    target = getattr(target, "value", target)
    if target not in LOAN_TRANSITIONS[loan.status]:
        raise Conflict(
            f"Недопустимый переход: запрос в статусе «{loan.get_status_display()}» "
            f"нельзя перевести в «{Loan.Status(target).label}»."
        )
    loan.status = target


def _save(loan, fields):
    try:
        with transaction.atomic():
            loan.save(update_fields=fields)
    except IntegrityError:
        raise Conflict("Экземпляр уже занят другим принятым запросом.")


@transaction.atomic
def request_loan(*, copy_id, borrower, requested_return_date, message=""):
    try:
        copy = Copy.objects.select_for_update().get(pk=copy_id)
    except Copy.DoesNotExist:
        raise NotFound("Экземпляр не найден.")

    if copy.owner_id == borrower.id:
        raise ValidationError({"copy": ["Нельзя запросить собственный экземпляр."]})

    today = timezone.localdate()
    if requested_return_date <= today:
        raise ValidationError({"requested_return_date": ["Дата возврата должна быть в будущем."]})
    if requested_return_date > today + timedelta(days=365):
        raise ValidationError({"requested_return_date": ["Срок не может превышать один год."]})

    if not copy.is_active:
        raise Conflict("Владелец снял этот экземпляр с полки.")
    if Loan.objects.filter(copy=copy, status__in=Loan.BUSY_STATUSES).exists():
        raise Conflict("Экземпляр сейчас занят: запрос уже принят или книга на руках.")
    if Loan.objects.filter(copy=copy, borrower=borrower, status=Loan.Status.PENDING).exists():
        raise Conflict("У вас уже есть ожидающий запрос на этот экземпляр.")

    loan = Loan.objects.create(
        copy=copy,
        borrower=borrower,
        requested_return_date=requested_return_date,
        message=message,
    )
    return _fresh(loan.pk)


@transaction.atomic
def accept_loan(loan_id, user):
    loan = _load_locked(loan_id, user)
    _require_owner(loan, user)
    _move(loan, Loan.Status.ACCEPTED)
    copy = loan.copy
    if not copy.is_active:
        raise Conflict("Экземпляр снят с полки.")
    if Loan.objects.filter(copy=copy, status__in=Loan.BUSY_STATUSES).exclude(pk=loan.pk).exists():
        raise Conflict("Экземпляр уже занят другим запросом: двух заёмщиков принять нельзя.")
    _save(loan, ["status"])
    Loan.objects.filter(copy=copy, status=Loan.Status.PENDING).exclude(pk=loan.pk).update(
        status=Loan.Status.REJECTED
    )
    return _fresh(loan.pk)


@transaction.atomic
def reject_loan(loan_id, user):
    loan = _load_locked(loan_id, user)
    _require_owner(loan, user)
    _move(loan, Loan.Status.REJECTED)
    _save(loan, ["status"])
    return _fresh(loan.pk)


@transaction.atomic
def cancel_loan(loan_id, user):
    """Отменить может заёмщик или владелец (ожидает / принята → отменена)."""
    loan = _load_locked(loan_id, user)
    _move(loan, Loan.Status.CANCELLED)
    _save(loan, ["status"])
    return _fresh(loan.pk)


@transaction.atomic
def hand_over_loan(loan_id, user):
    loan = _load_locked(loan_id, user)
    _require_owner(loan, user)
    _move(loan, Loan.Status.HANDED_OVER)
    loan.handed_at = timezone.now()
    _save(loan, ["status", "handed_at"])
    return _fresh(loan.pk)


@transaction.atomic
def return_loan(loan_id, user):
    loan = _load_locked(loan_id, user)
    _require_owner(loan, user)
    _move(loan, Loan.Status.RETURNED)
    loan.returned_at = timezone.now()
    _save(loan, ["status", "returned_at"])
    return _fresh(loan.pk)


def prepare_deactivation(copy):
    """Вызывать внутри transaction.atomic при заблокированном экземпляре."""
    if copy.loans.filter(status=Loan.Status.HANDED_OVER).exists():
        raise Conflict("Книга сейчас на руках: снять экземпляр с полки можно только после возврата.")
    if copy.loans.filter(status=Loan.Status.ACCEPTED).exists():
        raise Conflict("Есть принятый запрос: сначала отмените его или передайте книгу.")
    copy.loans.filter(status=Loan.Status.PENDING).update(status=Loan.Status.REJECTED)
