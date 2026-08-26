from rest_framework_simplejwt.authentication import JWTAuthentication as BaseJWTAuthentication

from apps.tenants.scope import scope_for_user, set_current_scope


class JWTAuthentication(BaseJWTAuthentication):
    """
    Sets the request's access scope as soon as DRF resolves the authenticated
    user — see apps.tenants.middleware.TenantMiddleware for why this can't be
    done at the Django-middleware layer.

    The scope is derived from the User row, never from token claims, so a role
    or tenant change takes effect immediately instead of at token expiry.
    """

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None:
            user, _token = result
            set_current_scope(scope_for_user(user))
        return result
