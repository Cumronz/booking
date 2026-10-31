from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone


class Book(models.Model):
    """Произведение — запись общего справочника (ведёт модератор)."""

    title = models.CharField("Название", max_length=255, db_index=True)
    author = models.CharField("Автор", max_length=255, db_index=True)
    genre = models.CharField("Жанр", max_length=100, db_index=True)
    description = models.TextField("Описание", blank=True)
    cover = models.ImageField("Обложка", upload_to="covers/", blank=True, null=True)
    search_key = models.CharField(max_length=600, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["title", "id"]

    def save(self, *args, **kwargs):
        self.title = self.title.strip()
        self.author = self.author.strip()
        self.genre = self.genre.strip()
        self.search_key = f"{self.title}|{self.author}".casefold()
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            kwargs["update_fields"] = set(update_fields) | {"title", "author", "genre", "search_key"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} — {self.author}"


class CopyQuerySet(models.QuerySet):
    def with_availability(self):
        """Добавляет is_busy: есть принятая или активная (переданная) передача."""
        busy = Loan.objects.filter(copy=OuterRef("pk"), status__in=Loan.BUSY_STATUSES)
        return self.annotate(is_busy=Exists(busy))


class Copy(models.Model):
    """Конкретный экземпляр книги на личной полке участника."""

    class Condition(models.TextChoices):
        NEW = "new", "Новая"
        GOOD = "good", "Хорошее"
        FAIR = "fair", "Удовлетворительное"
        WORN = "worn", "Потрёпанная"

    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="copies")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="copies")
    condition = models.CharField(max_length=10, choices=Condition.choices, default=Condition.GOOD)
    pickup_place = models.CharField("Место передачи", max_length=255)
    is_active = models.BooleanField("На полке", default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CopyQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["book", "is_active"], name="copy_book_active_idx"),
            models.Index(fields=["owner", "is_active"], name="copy_owner_active_idx"),
        ]

    def __str__(self):
        return f"#{self.pk} {self.book.title} ({self.owner})"


LOAN_TRANSITIONS = {
    "pending": {"accepted", "rejected", "cancelled"},
    "accepted": {"handed_over", "cancelled"},
    "handed_over": {"returned"},
    "rejected": set(),
    "cancelled": set(),
    "returned": set(),
}


class Loan(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        ACCEPTED = "accepted", "Принята"
        REJECTED = "rejected", "Отклонена"
        CANCELLED = "cancelled", "Отменена"
        HANDED_OVER = "handed_over", "Передана"
        RETURNED = "returned", "Возвращена"

    BUSY_STATUSES = ("accepted", "handed_over")

    copy = models.ForeignKey(Copy, on_delete=models.PROTECT, related_name="loans")
    borrower = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="borrowed_loans")
    requested_return_date = models.DateField("Желаемая дата возврата")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    message = models.CharField("Сообщение владельцу", max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    handed_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["status", "requested_return_date"], name="loan_status_due_idx"),
            models.Index(fields=["borrower", "status"], name="loan_borrower_status_idx"),
            models.Index(fields=["copy", "status"], name="loan_copy_status_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["copy"],
                condition=Q(status__in=["accepted", "handed_over"]),
                name="uniq_busy_loan_per_copy",
            ),
            models.UniqueConstraint(
                fields=["copy", "borrower"],
                condition=Q(status="pending"),
                name="uniq_pending_loan_per_borrower",
            ),
        ]

    @property
    def is_overdue(self) -> bool:
        return self.status == self.Status.HANDED_OVER and self.requested_return_date < timezone.localdate()

    def __str__(self):
        return f"Loan#{self.pk} {self.status}"


class ReadingEntry(models.Model):
    class Status(models.TextChoices):
        WANT = "want", "Хочу прочитать"
        READING = "reading", "Читаю"
        READ = "read", "Прочитал"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reading_entries")
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="reading_entries")
    status = models.CharField(max_length=10, choices=Status.choices)
    finished_at = models.DateField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        indexes = [models.Index(fields=["status", "finished_at"], name="reading_status_fin_idx")]
        constraints = [
            models.UniqueConstraint(fields=["user", "book"], name="uniq_reading_user_book"),
            models.CheckConstraint(
                condition=Q(status="read") | Q(finished_at__isnull=True),
                name="reading_finished_only_if_read",
            ),
        ]


class Review(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reviews")
    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name="reviews")
    score = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField(blank=True)
    is_hidden = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "book"], name="uniq_review_user_book"),
            models.CheckConstraint(condition=Q(score__gte=1, score__lte=5), name="review_score_1_5"),
        ]
        indexes = [models.Index(fields=["book", "is_hidden"], name="review_book_hidden_idx")]
