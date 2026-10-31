from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("books", views.BookViewSet, basename="book")
router.register("copies", views.CopyViewSet, basename="copy")
router.register("loans", views.LoanViewSet, basename="loan")
router.register("reviews", views.ReviewModerationViewSet, basename="review")

urlpatterns = [
    path("genres", views.GenreListView.as_view()),
    path("reading", views.ReadingListView.as_view()),
    path("reading/stats", views.ReadingStatsView.as_view()),
    path("reading/<int:book_id>", views.ReadingEntryView.as_view()),
] + router.urls
