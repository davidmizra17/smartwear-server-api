from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsEventOwnerOrSuperuser(BasePermission):
    """
    Object-level permission: read access for all authenticated users in the
    tenant; write access only for the event's creator or a superuser.
    """

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return request.user.is_superuser or obj.created_by_id == request.user.pk
