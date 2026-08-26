# Agentic Errors

## Architectural Errors/Inefficiencies

### 2026-08-01 — URL restructuring and schema separation

**Changes made:**

1. **Detached `UserViewSet` from the auth router** — `UserViewSet` was registered inside `apps/users/urls.py` which was mounted at `api/v1/auth/`, resulting in `/api/v1/auth/users/`. Users are a resource, not an auth concern. Moved to `/api/v1/users/` by splitting the urls module into a package: `apps/users/urls/auth.py` (token/refresh/me) and `apps/users/urls/users.py` (UserViewSet).

2. **Gave events its own URL prefix** — `apps/events/urls.py` was mounted at `api/v1/` alongside all other apps, relying on the router prefix string `"events"` to produce `/api/v1/events/`. This is fragile — the routing intent lives in two places (the mount point and the router prefix). Now the mount point alone is authoritative (`api/v1/events/`) and the router registers at `""`.

3. **Added explicit schema tags to ViewSets** — Without tags, drf-spectacular groups all endpoints under whatever the first URL segment resolves to, which was `v1` for everything. Added `@extend_schema_view` tags so `UserViewSet` appears under `users`, `EventViewSet` under `events`, and the three auth endpoints remain under `v1`. This makes the Swagger UI usable as an actual API reference.

**Why this matters long term:**

Mixing resource APIs into an auth namespace makes onboarding harder, breaks REST client conventions, and creates pressure to keep adding unrelated routes under `auth/` out of inertia. Separating concerns at the URL level — auth handles identity, resource endpoints handle data — keeps each router file focused and makes it straightforward to apply different middleware, rate limits, or permissions per namespace in the future.

---

## Security & Authorization Defects (found by automated code review, 2026-08-01)

Errors are grouped by type. All were present in the codebase before PR #2 and fixed as part of it.

---

### Tenant Isolation Failures

**`TenantScopedManager` returned all rows for tenantless users**
- File: `apps/orders/managers.py`
- Severity: Blocking
- The manager guarded with `if tenant is not None: filter(...)` — the else branch returned the full unscoped queryset. Any user with no tenant (Master role) calling `GET /api/v1/events/` or `GET /api/v1/orders/` received every row in the database, across all tenants.
- Fix: flipped to `if tenant is None: return qs.none()` — the manager is now safe by default for all models using it.

**`UserViewSet` exposed superuser accounts to Master users**
- File: `apps/users/views.py`
- Severity: Blocking
- `get_queryset` for non-superusers did `filter(tenant=user.tenant)`. Master has `tenant=None`, so this became `filter(tenant=None)`, returning all other Masters and superuser accounts. With no `has_object_permission` override, a Master could then PATCH any superuser record.
- Fix: added `if not user.tenant_id: return User.objects.none()` guard before the filter.

**Schema endpoints were publicly accessible**
- File: `config/urls.py`
- Severity: Should fix (treated as blocking given multi-tenant context)
- `/api/schema/`, `/api/docs/`, and `/api/redoc/` had no `permission_classes`, making the full API surface — all routes, request/response shapes, security schemes — publicly browsable without authentication.
- Fix: added `permission_classes=[IsAuthenticated]` to all three views.

---

### Logic Errors Causing Runtime Crashes (500s)

**`perform_create` in `UserViewSet` silently nulled the tenant from payload**
- File: `apps/users/views.py`
- Severity: Blocking (data integrity)
- `serializer.save(tenant=tenant)` was called with `tenant=None` for both superusers and Masters (neither has a tenant). `serializer.save(**kwargs)` merges kwargs into `validated_data` before calling `create()`, overwriting whatever tenant the client sent in the payload. Every user created via the API had `tenant=None` regardless of what was submitted.
- Fix: deleted `perform_create` entirely — the serializer already handles the tenant field correctly from the validated payload.

**`EventViewSet.perform_create` crashed with IntegrityError for tenantless users**
- File: `apps/events/views.py`
- Severity: Should fix
- `serializer.save(client=self.request.user.tenant, ...)` with `tenant=None` and a non-nullable `client` FK hit a DB IntegrityError, returning a 500 instead of a clean validation error.
- Fix: added `if not self.request.user.tenant_id: raise PermissionDenied(...)` before the save.

---

### Privilege Escalation

**Masters could assign `role=Master` via the user creation endpoint**
- File: `apps/users/serializers.py`
- Severity: Should fix
- `role` was a fully writable field in `UserManagementSerializer` with no validation. A Master could `POST /api/v1/users/` with `role=Master` and create another Master-role account, effectively self-replicating privilege.
- Fix: added `validate_role()` that raises `ValidationError` if `role=Master` is set by a non-superuser.

---

### Data Integrity / Silent Misconfiguration

**Email not normalized on user creation or update**
- File: `apps/users/serializers.py`
- Severity: Should fix
- `UserManagementSerializer.create` built `User(**validated_data)` directly, bypassing `UserManager.create_user` which calls `normalize_email`. Case variants of the same email (`User@Example.COM` vs `user@example.com`) could coexist and bypass the `unique=True` constraint depending on DB collation. Same issue existed in `update`.
- Fix: `validated_data["email"] = User.objects.normalize_email(...)` added to both `create` and `update`.

**Operators could be created without a tenant**
- File: `apps/users/serializers.py`
- Severity: Should fix
- `tenant` was not required in `UserManagementSerializer`. A superuser could create an Operator with no tenant; that operator would silently see zero data everywhere with no error indicating misconfiguration.
- Fix: added cross-field `validate()` that raises an error if `role=Operator` and no tenant is provided, handling both create and partial update (PATCH) via `getattr(self.instance, ...)`.

---

### N+1 Query

**`UserViewSet` list triggered a query per user for tenant**
- File: `apps/users/views.py`
- Severity: Should fix
- `UserManagementSerializer` includes `tenant` in its fields but the queryset had no `select_related("tenant")`, causing one extra query per user in the list response.
- Fix: added `select_related("tenant")` to both queryset branches.

---

### Intra-Tenant Authorization Gap

**Any operator could modify or delete events created by other operators in the same tenant**
- File: `apps/events/views.py`
- Severity: Should fix
- `EventViewSet` is a full `ModelViewSet`. `get_queryset` scoped by tenant correctly, but there was no object-level check on `created_by` — any tenant member could PATCH or DELETE any event in their tenant.
- Fix: added `IsEventOwnerOrSuperuser` permission class (`has_object_permission` checks `obj.created_by_id == request.user.pk`).

---

### Agentic Regression (introduced and fixed in same session)

**`EventSerializer.product_id` filtered by `client_id` on `Product` which has no such field**
- File: `apps/events/serializers.py`
- Severity: Blocking (regression)
- When scoping the `product_id` queryset per tenant, a grep output was misread — the `client` FK belongs to `Order`, not `Product`. `Product` is a global catalog with no tenant relationship. The filter `Product.objects.filter(client_id=...)` raised `FieldError` at runtime for every non-superuser event write.
- Fix: reverted to `Product.objects.all()` with a comment documenting that Product is a shared catalog.
- **Note:** This error was introduced by the agent in the same session and caught by the automated reviewer on the next pass.
