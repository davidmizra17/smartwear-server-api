
from contextvars import ContextVar

_current_tenant: ContextVar = ContextVar("current_tenant", default=None)


def get_current_tenant():
    return _current_tenant.get()


def set_current_tenant(tenant):
    _current_tenant.set(tenant)


class TenantMiddleware:
    """
    Only owns the request-scoped lifecycle of the tenant ContextVar (reset on
    exit, to avoid leaking across requests on a reused worker thread). It
    cannot set the tenant itself: DRF views authenticate via JWT lazily,
    inside the view, after this middleware has already run — at this point
    `request.user` is still Django's own AnonymousUser. The actual tenant is
    set by `apps.tenants.authentication.JWTAuthentication` once it resolves
    the authenticated user.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = _current_tenant.set(None)
        try:
            response = self.get_response(request)
        finally:
            _current_tenant.reset(token)

        return response
