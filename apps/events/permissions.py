from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsEventOwnerOrSuperuser(BasePermission):
    """
    Object-level permission: restricts write operations (PUT/PATCH/DELETE) to
    the event's creator or a superuser. Read access and create are handled by
    IsAuthenticated and perform_create respectively — this class does not cover them.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or obj.created_by_id == request.user.pk
