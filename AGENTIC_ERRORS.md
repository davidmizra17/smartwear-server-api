# Agentic Errors

## Architectural Errors/Inefficiencies

### 2026-08-01 — URL restructuring and schema separation

**Changes made:**

1. **Detached `UserViewSet` from the auth router** — `UserViewSet` was registered inside `apps/users/urls.py` which was mounted at `api/v1/auth/`, resulting in `/api/v1/auth/users/`. Users are a resource, not an auth concern. Moved to `/api/v1/users/` by splitting the urls module into a package: `apps/users/urls/auth.py` (token/refresh/me) and `apps/users/urls/users.py` (UserViewSet).

2. **Gave events its own URL prefix** — `apps/events/urls.py` was mounted at `api/v1/` alongside all other apps, relying on the router prefix string `"events"` to produce `/api/v1/events/`. This is fragile — the routing intent lives in two places (the mount point and the router prefix). Now the mount point alone is authoritative (`api/v1/events/`) and the router registers at `""`.

3. **Added explicit schema tags to ViewSets** — Without tags, drf-spectacular groups all endpoints under whatever the first URL segment resolves to, which was `v1` for everything. Added `@extend_schema_view` tags so `UserViewSet` appears under `users`, `EventViewSet` under `events`, and the three auth endpoints remain under `v1`. This makes the Swagger UI usable as an actual API reference.

**Why this matters long term:**

Mixing resource APIs into an auth namespace makes onboarding harder, breaks REST client conventions, and creates pressure to keep adding unrelated routes under `auth/` out of inertia. Separating concerns at the URL level — auth handles identity, resource endpoints handle data — keeps each router file focused and makes it straightforward to apply different middleware, rate limits, or permissions per namespace in the future.
