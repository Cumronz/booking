from django.urls import path
from rest_framework.routers import SimpleRouter

from . import views

router = SimpleRouter(trailing_slash=False)
router.register("users", views.UserAdminViewSet, basename="user")

urlpatterns = [
    path("auth/register", views.RegisterView.as_view()),
    path("auth/login", views.LoginView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/me", views.MeView.as_view()),
    path("auth/change-password", views.ChangePasswordView.as_view()),
] + router.urls
