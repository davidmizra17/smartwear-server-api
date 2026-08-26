from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication

from apps.tenants.middleware import set_current_tenant


class JWTAuthentication(BaseJWTAuthentication):
    """
    Sets the request's tenant ContextVar as soon as DRF resolves the
    authenticated user — see apps.tenants.middleware.TenantMiddleware for
    why this can't be done at the Django-middleware layer.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            set_current_tenant(getattr(user, "tenant", None))
        return result
