from apps.tenants.scope import DenyAll, reset_current_scope, set_current_scope


class TenantMiddleware:
    """
    Only owns the request-scoped lifecycle of the access-scope ContextVar
    (reset on exit, to avoid leaking across requests on a reused worker
    thread). It cannot resolve the scope itself: DRF views authenticate via
    JWT lazily, inside the view, after this middleware has already run — at
    this point `request.user` is still Django's own AnonymousUser. The real
    scope is set by `apps.tenants.authentication.JWTAuthentication` once it
    resolves the authenticated user.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_current_scope(DenyAll())
        try:
            response = self.get_response(request)
        finally:
            reset_current_scope(token)

        return response
