
import threading

_thread_locals = threading.local()


def get_current_tenant():
    return getattr(_thread_locals, "tenant", None)


class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tenant = None
        if hasattr(request, "user") and request.user.is_authenticated:
            tenant = request.user.tenant

        _thread_locals.tenant = tenant
        request.tenant = tenant

        response = self.get_response(request)

        _thread_locals.tenant = None
        return response
