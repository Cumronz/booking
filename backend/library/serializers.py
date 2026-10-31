from django.utils import timezone
from rest_framework import serializers

from accounts.serializers import UserBriefSerializer

from .models import Book, Copy, Loan, ReadingEntry, Review


class BookSerializer(serializers.ModelSerializer):
    avg_rating = serializers.SerializerMethodField()
    reviews_count = serializers.SerializerMethodField()
    copies_total = serializers.SerializerMethodField()
    available_copies = serializers.SerializerMethodField()
    read_this_month = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = [
            "id", "title", "author", "genre", "description", "cover", "created_at",
            "avg_rating", "reviews_count", "copies_total", "available_copies", "read_this_month",
        ]
        read_only_fields = ["id", "created_at"]

    def get_avg_rating(self, obj):
        value = getattr(obj, "avg_rating", None)
        return None if value is None else round(float(value), 2)

    def get_reviews_count(self, obj):
        return getattr(obj, "reviews_count", 0)

    def get_copies_total(self, obj):
        return getattr(obj, "copies_total", 0)

    def get_available_copies(self, obj):
        return getattr(obj, "available_copies", 0)

    def get_read_this_month(self, obj):
        return getattr(obj, "read_this_month", 0)

    def validate(self, attrs):
        title = attrs.get("title", getattr(self.instance, "title", ""))
        author = attrs.get("author", getattr(self.instance, "author", ""))
        key = f"{title.strip()}|{author.strip()}".casefold()
        duplicates = Book.objects.filter(search_key=key)
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise serializers.ValidationError({"title": ["Такая книга этого автора уже есть в каталоге."]})
        return attrs


class BookDetailSerializer(BookSerializer):
    my_review = serializers.SerializerMethodField()
    my_reading = serializers.SerializerMethodField()

    class Meta(BookSerializer.Meta):
        fields = BookSerializer.Meta.fields + ["my_review", "my_reading"]

    def get_my_review(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        review = Review.objects.filter(user=request.user, book=obj).first()
        return ReviewSerializer(review).data if review else None

    def get_my_reading(self, obj):
        request = self.context.get("request")
        if not request:
            return None
        entry = ReadingEntry.objects.filter(user=request.user, book=obj).first()
        return ReadingEntrySerializer(entry).data if entry else None


class BookBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Book
        fields = ["id", "title", "author", "cover"]


class CopySerializer(serializers.ModelSerializer):
    owner = UserBriefSerializer(read_only=True)
    book = serializers.PrimaryKeyRelatedField(queryset=Book.objects.all())
    book_title = serializers.CharField(source="book.title", read_only=True)
    book_author = serializers.CharField(source="book.author", read_only=True)
    condition_display = serializers.CharField(source="get_condition_display", read_only=True)
    available = serializers.SerializerMethodField()

    class Meta:
        model = Copy
        fields = [
            "id", "book", "book_title", "book_author", "owner", "condition", "condition_display",
            "pickup_place", "is_active", "available", "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_available(self, obj):
        busy = getattr(obj, "is_busy", None)
        if busy is None:
            busy = obj.loans.filter(status__in=Loan.BUSY_STATUSES).exists()
        return bool(obj.is_active and not busy)

    def validate_pickup_place(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Укажите место передачи.")
        return value

    def validate(self, attrs):
        if self.instance is not None and "book" in attrs and attrs["book"].pk != self.instance.book_id:
            raise serializers.ValidationError({"book": ["Книгу у существующего экземпляра менять нельзя."]})
        return attrs


class LoanSerializer(serializers.ModelSerializer):
    book = BookBriefSerializer(source="copy.book", read_only=True)
    owner = UserBriefSerializer(source="copy.owner", read_only=True)
    borrower = UserBriefSerializer(read_only=True)
    copy_id = serializers.IntegerField(read_only=True)
    pickup_place = serializers.CharField(source="copy.pickup_place", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)
    days_overdue = serializers.SerializerMethodField()
    available_actions = serializers.SerializerMethodField()

    class Meta:
        model = Loan
        fields = [
            "id", "copy_id", "book", "owner", "borrower", "pickup_place",
            "requested_return_date", "status", "status_display", "message",
            "created_at", "handed_at", "returned_at",
            "is_overdue", "days_overdue", "available_actions",
        ]
        read_only_fields = fields

    def get_days_overdue(self, obj):
        if not obj.is_overdue:
            return 0
        return (timezone.localdate() - obj.requested_return_date).days

    def get_available_actions(self, obj):
        request = self.context.get("request")
        if not request:
            return []
        uid = request.user.id
        is_owner = obj.copy.owner_id == uid
        is_borrower = obj.borrower_id == uid
        actions = []
        if is_owner:
            if obj.status == "pending":
                actions += ["accept", "reject"]
            elif obj.status == "accepted":
                actions += ["hand-over", "cancel"]
            elif obj.status == "handed_over":
                actions.append("return")
        if is_borrower and obj.status in ("pending", "accepted"):
            actions.append("cancel")
        return actions


class LoanCreateSerializer(serializers.Serializer):
    requested_return_date = serializers.DateField()
    message = serializers.CharField(required=False, allow_blank=True, max_length=500, default="")


class ReadingEntrySerializer(serializers.ModelSerializer):
    book = BookBriefSerializer(read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = ReadingEntry
        fields = ["id", "book", "status", "status_display", "finished_at", "updated_at"]
        read_only_fields = fields


class ReadingInputSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ReadingEntry.Status.choices)
    finished_at = serializers.DateField(required=False, allow_null=True)

    def validate(self, attrs):
        finished = attrs.get("finished_at")
        today = timezone.localdate()
        if attrs["status"] != ReadingEntry.Status.READ:
            if finished:
                raise serializers.ValidationError(
                    {"finished_at": ["Дату завершения можно указать только для статуса «Прочитал»."]}
                )
            attrs["finished_at"] = None
        else:
            finished = finished or today
            if finished > today:
                raise serializers.ValidationError({"finished_at": ["Дата завершения не может быть в будущем."]})
            attrs["finished_at"] = finished
        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)
    book_title = serializers.CharField(source="book.title", read_only=True)

    class Meta:
        model = Review
        fields = ["id", "user", "book", "book_title", "score", "text", "is_hidden", "created_at", "updated_at"]
        read_only_fields = fields


class ReviewInputSerializer(serializers.Serializer):
    score = serializers.IntegerField(min_value=1, max_value=5)
    text = serializers.CharField(required=False, allow_blank=True, max_length=5000, default="")
