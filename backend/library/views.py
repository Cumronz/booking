from datetime import date

from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, Exists, F, FloatField, IntegerField, OuterRef, Q, Subquery
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsModerator

from . import services
from .exceptions import Conflict
from .models import Book, Copy, Loan, ReadingEntry, Review
from .pagination import StandardPagination
from .serializers import (
    BookDetailSerializer,
    BookSerializer,
    CopySerializer,
    LoanCreateSerializer,
    LoanSerializer,
    ReadingEntrySerializer,
    ReadingInputSerializer,
    ReviewInputSerializer,
    ReviewSerializer,
)

TRUE_VALUES = {"1", "true", "yes", "on"}


def flag(request, name):
    return request.query_params.get(name, "").lower() in TRUE_VALUES


def _count_sq(qs):
    """Подзапрос-счётчик по book (без размножения строк, как при JOIN-агрегатах)."""
    sq = qs.order_by().values("book").annotate(c=Count("pk")).values("c")[:1]
    return Coalesce(Subquery(sq, output_field=IntegerField()), 0)


class BookViewSet(viewsets.ModelViewSet):
    """Справочник: читают все авторизованные, ведёт модератор."""

    lookup_value_regex = r"\d+"

    ORDERING = {
        "title": ["title", "id"],
        "-title": ["-title", "id"],
        "author": ["author", "title"],
        "-author": ["-author", "title"],
        "created_at": ["created_at", "id"],
        "-created_at": ["-created_at", "-id"],
    }

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsModerator()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        return BookDetailSerializer if self.action == "retrieve" else BookSerializer

    def get_queryset(self):
        today = timezone.localdate()
        busy = Loan.objects.filter(copy=OuterRef("pk"), status__in=Loan.BUSY_STATUSES)
        visible_reviews = Review.objects.filter(book=OuterRef("pk"), is_hidden=False)

        qs = Book.objects.annotate(
            avg_rating=Subquery(
                visible_reviews.order_by().values("book").annotate(a=Avg("score")).values("a")[:1],
                output_field=FloatField(),
            ),
            reviews_count=_count_sq(visible_reviews),
            copies_total=_count_sq(Copy.objects.filter(book=OuterRef("pk"), is_active=True)),
            available_copies=_count_sq(
                Copy.objects.filter(book=OuterRef("pk"), is_active=True).filter(~Exists(busy))
            ),
            read_this_month=_count_sq(
                ReadingEntry.objects.filter(
                    book=OuterRef("pk"),
                    status=ReadingEntry.Status.READ,
                    finished_at__year=today.year,
                    finished_at__month=today.month,
                )
            ),
        )

        p = self.request.query_params
        search = p.get("search", "").strip()
        if search:
            qs = qs.filter(search_key__contains=search.casefold())
        genre = p.get("genre", "").strip()
        if genre:
            qs = qs.filter(genre=genre)
        if flag(self.request, "available"):
            qs = qs.filter(available_copies__gt=0)

        ordering = p.get("ordering", "title")
        if ordering in ("avg_rating", "-avg_rating"):
            expr = F("avg_rating").desc(nulls_last=True) if ordering.startswith("-") else F("avg_rating").asc(nulls_last=True)
            return qs.order_by(expr, "title")
        return qs.order_by(*self.ORDERING.get(ordering, self.ORDERING["title"]))

    def _fresh(self, pk):
        annotated = self.get_queryset().get(pk=pk)
        return BookDetailSerializer(annotated, context=self.get_serializer_context()).data

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        book = serializer.save()
        return Response(self._fresh(book.pk), status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(self._fresh(instance.pk))

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            raise Conflict(
                "У книги есть экземпляры, отзывы или записи чтения — удалить её нельзя, "
                "история обменов сохраняется."
            )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["get"], url_path="reviews")
    def reviews(self, request, pk=None):
        book = get_object_or_404(Book, pk=pk)
        qs = (
            Review.objects.filter(book=book)
            .filter(Q(is_hidden=False) | Q(user=request.user))
            .select_related("user", "book")
        )
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(ReviewSerializer(page, many=True, context={"request": request}).data)

    @action(detail=True, methods=["put", "delete"], url_path="review")
    def review(self, request, pk=None):
        """PUT /books/{id}/review — создать или изменить свою рецензию (одна на пару пользователь/книга)."""
        book = get_object_or_404(Book, pk=pk)
        if request.method == "DELETE":
            deleted, _ = Review.objects.filter(user=request.user, book=book).delete()
            if not deleted:
                return Response({"detail": "У вас нет рецензии на эту книгу."}, status=status.HTTP_404_NOT_FOUND)
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = ReviewInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                review, created = Review.objects.update_or_create(
                    user=request.user,
                    book=book,
                    defaults={"score": serializer.validated_data["score"], "text": serializer.validated_data["text"]},
                )
        except IntegrityError:
            raise Conflict("Не удалось сохранить рецензию, повторите запрос.")
        return Response(
            ReviewSerializer(review).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], url_path="copies")
    def copies(self, request, pk=None):
        book = get_object_or_404(Book, pk=pk)
        qs = Copy.objects.filter(book=book, is_active=True).select_related("book", "owner").with_availability()
        page = self.paginate_queryset(qs)
        return self.get_paginated_response(CopySerializer(page, many=True, context={"request": request}).data)


class GenreListView(APIView):
    def get(self, request):
        rows = Book.objects.values("genre").annotate(count=Count("id")).order_by("genre")
        return Response(list(rows))


class IsCopyOwner(BasePermission):
    message = "Менять экземпляр может только его владелец."

    def has_object_permission(self, request, view, obj):
        return obj.owner_id == request.user.id


class CopyViewSet(viewsets.ModelViewSet):
    serializer_class = CopySerializer
    lookup_value_regex = r"\d+"

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsCopyOwner()]
        return [IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        qs = Copy.objects.select_related("book", "owner").with_availability()
        qs = qs.filter(Q(is_active=True) | Q(owner=user))
        p = self.request.query_params
        if flag(self.request, "mine"):
            qs = qs.filter(owner=user)
        if p.get("book"):
            qs = qs.filter(book_id=p["book"])
        if flag(self.request, "available"):
            qs = qs.filter(is_active=True, is_busy=False)
        return qs

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

    def perform_update(self, serializer):
        with transaction.atomic():
            copy = Copy.objects.select_for_update().get(pk=serializer.instance.pk)
            wants_inactive = "is_active" in serializer.validated_data and not serializer.validated_data["is_active"]
            if copy.is_active and wants_inactive:
                services.prepare_deactivation(copy)
            serializer.save()

    def destroy(self, request, *args, **kwargs):
        copy = self.get_object()
        with transaction.atomic():
            locked = Copy.objects.select_for_update().get(pk=copy.pk)
            if locked.loans.filter(status=Loan.Status.HANDED_OVER).exists():
                raise Conflict("Книга на руках: удалить экземпляр можно только после возврата.")
            if locked.loans.exists():
                raise Conflict("У экземпляра есть история передач — удалить его нельзя, снимите его с полки.")
            locked.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="loans")
    def loans(self, request, pk=None):
        """POST /copies/{id}/loans — запрос на книгу с датой возврата."""
        serializer = LoanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = services.request_loan(copy_id=pk, borrower=request.user, **serializer.validated_data)
        return Response(LoanSerializer(loan, context={"request": request}).data, status=status.HTTP_201_CREATED)


class LoanViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = LoanSerializer
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        user = self.request.user
        qs = Loan.objects.select_related("copy__book", "copy__owner", "borrower")
        role = self.request.query_params.get("role")
        if role == "incoming":
            qs = qs.filter(copy__owner=user)
        elif role == "outgoing":
            qs = qs.filter(borrower=user)
        else:
            qs = qs.filter(Q(copy__owner=user) | Q(borrower=user))
        statuses = [s for s in self.request.query_params.get("status", "").split(",") if s]
        if statuses:
            qs = qs.filter(status__in=statuses)
        if flag(self.request, "overdue"):
            qs = qs.filter(status=Loan.Status.HANDED_OVER, requested_return_date__lt=timezone.localdate())
        return qs

    def _respond(self, loan):
        return Response(LoanSerializer(loan, context={"request": self.request}).data)

    @action(detail=True, methods=["post"], url_path="accept")
    def accept(self, request, pk=None):
        return self._respond(services.accept_loan(pk, request.user))

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        return self._respond(services.reject_loan(pk, request.user))

    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        return self._respond(services.cancel_loan(pk, request.user))

    @action(detail=True, methods=["post"], url_path="hand-over")
    def hand_over(self, request, pk=None):
        return self._respond(services.hand_over_loan(pk, request.user))

    @action(detail=True, methods=["post"], url_path="return")
    def return_book(self, request, pk=None):
        return self._respond(services.return_loan(pk, request.user))


class ReadingListView(APIView):
    def get(self, request):
        qs = ReadingEntry.objects.filter(user=request.user).select_related("book")
        st = request.query_params.get("status")
        if st:
            qs = qs.filter(status=st)
        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response(ReadingEntrySerializer(page, many=True).data)


class ReadingEntryView(APIView):
    def get(self, request, book_id):
        entry = get_object_or_404(ReadingEntry.objects.select_related("book"), user=request.user, book_id=book_id)
        return Response(ReadingEntrySerializer(entry).data)

    def put(self, request, book_id):
        """PUT /reading/{book_id} — одна запись на пару пользователь/книга."""
        book = get_object_or_404(Book, pk=book_id)
        serializer = ReadingInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                entry, created = ReadingEntry.objects.update_or_create(
                    user=request.user,
                    book=book,
                    defaults={
                        "status": serializer.validated_data["status"],
                        "finished_at": serializer.validated_data["finished_at"],
                    },
                )
        except IntegrityError:
            raise Conflict("Не удалось сохранить запись, повторите запрос.")
        entry = ReadingEntry.objects.select_related("book").get(pk=entry.pk)
        return Response(ReadingEntrySerializer(entry).data, status=201 if created else 200)

    def delete(self, request, book_id):
        deleted, _ = ReadingEntry.objects.filter(user=request.user, book_id=book_id).delete()
        if not deleted:
            return Response({"detail": "Записи о чтении нет."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ReadingStatsView(APIView):
    def get(self, request):
        today = timezone.localdate()
        entries = ReadingEntry.objects.filter(user=request.user)
        by_status = {value: 0 for value, _ in ReadingEntry.Status.choices}
        for row in entries.values("status").annotate(c=Count("id")):
            by_status[row["status"]] = row["c"]

        read = entries.filter(status=ReadingEntry.Status.READ)

        months = []
        y, m = today.year, today.month
        for _ in range(6):
            months.append((y, m))
            m -= 1
            if m == 0:
                y, m = y - 1, 12
        months.reverse()
        counts = {
            (row["m"].year, row["m"].month): row["c"]
            for row in read.filter(finished_at__gte=date(months[0][0], months[0][1], 1))
            .annotate(m=TruncMonth("finished_at"))
            .values("m")
            .annotate(c=Count("id"))
        }
        return Response(
            {
                "by_status": by_status,
                "read_this_month": read.filter(finished_at__year=today.year, finished_at__month=today.month).count(),
                "read_this_year": read.filter(finished_at__year=today.year).count(),
                "months": [{"month": f"{y}-{m:02d}", "count": counts.get((y, m), 0)} for y, m in months],
            }
        )


class ReviewModerationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsModerator]
    lookup_value_regex = r"\d+"
    serializer_class = ReviewSerializer

    def get_queryset(self):
        qs = Review.objects.select_related("user", "book")
        p = self.request.query_params
        hidden = p.get("hidden")
        if hidden is not None and hidden != "":
            qs = qs.filter(is_hidden=hidden.lower() in TRUE_VALUES)
        if p.get("book"):
            qs = qs.filter(book_id=p["book"])
        return qs

    def _set_hidden(self, request, value):
        review = self.get_object()
        if review.is_hidden != value:
            review.is_hidden = value
            review.save(update_fields=["is_hidden"])
        return Response(ReviewSerializer(review).data)

    @action(detail=True, methods=["post"], url_path="hide")
    def hide(self, request, pk=None):
        return self._set_hidden(request, True)

    @action(detail=True, methods=["post"], url_path="unhide")
    def unhide(self, request, pk=None):
        return self._set_hidden(request, False)
