from rest_framework.permissions import BasePermission


class IsModerator(BasePermission):
    message = "Требуется роль модератора."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_moderator)


class IsAdminRole(BasePermission):
    message = "Требуется роль администратора."

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_admin_role)
