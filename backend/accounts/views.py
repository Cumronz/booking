from django.db.models import Q
from rest_framework import mixins, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from library.exceptions import Conflict

from .models import User
from .permissions import IsAdminRole
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    RegisterSerializer,
    RoleSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


class LogoutView(APIView):
    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class ChangePasswordView(APIView):
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
        return Response({"token": token.key})


class UserAdminViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Список пользователей и назначение ролей — только администратор."""

    permission_classes = [IsAdminRole]
    serializer_class = UserSerializer
    lookup_value_regex = r"\d+"

    def get_queryset(self):
        qs = User.objects.order_by("username")
        q = self.request.query_params.get("search", "").strip()
        if q:
            qs = qs.filter(Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
        role = self.request.query_params.get("role")
        if role:
            qs = qs.filter(role=role)
        return qs

    @action(detail=True, methods=["patch"], url_path="role")
    def set_role(self, request, pk=None):
        target = self.get_object()
        serializer = RoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if target.pk == request.user.pk:
            raise Conflict("Нельзя изменить собственную роль.")
        if target.is_superuser:
            raise Conflict("Роль суперпользователя изменить нельзя.")
        target.role = serializer.validated_data["role"]
        target.save(update_fields=["role"])
        return Response(UserSerializer(target).data)
