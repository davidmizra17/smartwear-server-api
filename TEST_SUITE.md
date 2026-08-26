# Test Suite

Reference for the 47 tests currently in the project, what each one guards, and
where the gaps are.

**Run:**

```bash
docker compose run --rm --no-deps -v "$PWD:/app" server python manage.py test
```

The `-v "$PWD:/app"` mount is required — `docker-compose.yml` declares no
volume, so without it the container runs a stale copy baked in at build time and
any files it writes (migrations, coverage) never reach the host.

Tests run under `config.test_runner.UnmanagedModelTestRunner`, which creates
tables for `managed = False` models (`apps.orders.Product`) so the legacy
ingestion-owned schema is testable.

**Status as of 2026-08-26: 47 passing, 0 failing.** System check clean.

## Layout

| File | Tests | Covers |
|---|---:|---|
| `apps/orders/tests.py` | 40 | Order read/write permissions, tenant isolation, independent customers, scope resolution, order submit + email |
| `apps/events/tests.py` | 7 | OrderLine (product picker) CRUD and validation |
| **Total** | **47** | |

`apps/catalog`, `apps/tenants`, and `apps/users` have no test module — see
[Known gaps](#known-gaps).

---

## `apps/orders/tests.py`

All API-level classes inherit `OrderTestsBase`, whose `setUp` builds two
tenants (`Client A`, `Client B`), an Operator and a Master on tenant A, a Master
on tenant B, and one Event + Order per tenant. `_auth(email, password)` obtains
a real JWT via `POST /api/v1/auth/token/` and sets the bearer header, so every
API test exercises the true authentication path — including the
`JWTAuthentication` hook that resolves the request's access scope.

### `TenantIsolationTests` (3)

The core multi-tenant boundary. These are the regression guard for the
historical bug where a tenantless context returned the full unscoped queryset.

| Test | Asserts |
|---|---|
| `test_user_a_cannot_see_user_b_orders` | Operator on tenant A lists orders: A's order present, B's absent. |
| `test_user_cannot_fetch_other_tenant_order_detail` | Direct GET of another tenant's order id → **404**, not 403 — the row is invisible, so its existence isn't disclosed. |
| `test_master_cannot_change_status_of_other_tenant_order` | Master of tenant B PATCHing tenant A's order → **404**. Elevated role does not cross the tenant edge. |

### `AuthTests` (1)

| Test | Asserts |
|---|---|
| `test_unauthenticated_request_rejected` | `GET /api/v1/orders/` with no credentials → **401**. |

### `ReadAccessTests` (2)

| Test | Asserts |
|---|---|
| `test_operator_can_list_own_tenant_orders` | Operator sees exactly 1 order, status `pending`. The positive counterpart to the isolation tests — proves scoping filters *to* the tenant, not to nothing. |
| `test_order_detail_includes_event_summary` | `event_title` is denormalized into the order payload (`"Evento A"`), so clients need no second request. |

### `StatusWritePermissionTests` (4)

Order status is Master-only; the Operator who creates an order cannot advance it.

| Test | Asserts |
|---|---|
| `test_operator_cannot_change_status` | Operator PATCH → **403**, and status is unchanged after `refresh_from_db()` (verifies no partial write). |
| `test_master_can_change_status_of_same_tenant_order` | Master of tenant A PATCHes A's order → **200**, status becomes `ordered`. |
| `test_operator_cannot_use_put` | PUT → **403**. `http_method_names` excludes `put`, so full replacement can't bypass the partial-update permission. |
| `test_delete_not_allowed` | DELETE by a Master → **405**. Orders are never destroyed via the API. |

> `test_master_can_change_status_of_same_tenant_order` is load-bearing beyond its
> own assertion: it proves Masters may hold a tenant and stay tenant-scoped. See
> `test_tenant_master_stays_tenant_scoped` below.

### `EventCreationAutoCreatesOrderTests` (2)

| Test | Asserts |
|---|---|
| `test_creating_event_auto_creates_order` | `POST /api/v1/events/` implicitly creates the paired Order with status `pending` and `client_id` copied from the event. Order is never created directly. |
| `test_event_serializer_does_not_expose_status` | `status` is absent from the Event payload — the deprecated `Event.status` field must not leak now that `Order.status` is authoritative. |

### `IndependentCustomerTests` (7)

Independent customers are users with **no tenant** who act on their own behalf.
Their rows carry `client = NULL` and are scoped by `created_by`
(`apps.tenants.scope.OwnerScope`). `setUp` adds two such users plus one
independent Event + Order, on top of the two-tenant base fixture — so every
assertion runs with tenant data and a second independent present as bait.

| Test | Asserts |
|---|---|
| `test_independent_can_create_event_and_order` | Independent POSTs an event → **201**, and the auto-created order has `client_id IS NULL`. This is the requirement itself. |
| `test_independent_sees_own_orders` | Order list is **exactly** `[own order]` — an equality assertion, not a membership one, so extra rows fail. |
| `test_independent_cannot_see_other_independents_orders` | The second independent does not see the first's order. Both have `tenant = None`, so this is the test that a shared null tenant is not a shared visibility group. |
| `test_independent_cannot_see_tenant_orders` | Neither tenant A's nor tenant B's orders appear. |
| `test_tenant_operator_cannot_see_independent_orders` | The reverse direction: tenant-scoped users don't see the tenantless space. |
| `test_independent_cannot_fetch_tenant_order_detail` | Direct GET of a tenant order → **404**. |
| `test_independent_sees_own_events_only` | Same isolation holds on `/api/v1/events/`, not just orders. |

### `ScopeResolutionTests` (7)

Unit-level guards on the scope↔manager contract, asserted directly against
`scope_for_user()` and the managers without going through a request. These
encode the fail-closed *structure*, which API tests can't reach (an API test
always has an authenticated user; these cover the contexts that don't).

| Test | Asserts |
|---|---|
| `test_tenant_master_stays_tenant_scoped` | A Master **with** a tenant resolves to `TenantScope`, not `DenyAll`. Regression guard: resolving role before tenant would silently blank out every Master who holds a tenant, breaking `test_master_can_change_status_of_same_tenant_order`. This is why `scope_for_user` checks tenant first. |
| `test_tenantless_master_and_superuser_deny` | Tenantless Master and superuser both resolve to `DenyAll` — privileged accounts see nothing by default and must opt into `.unscoped` explicitly. |
| `test_independent_resolves_to_owner_scope` | Tenantless Operator resolves to `OwnerScope(user.pk)`. |
| `test_no_scope_context_denies` | With no scope ever set — Celery tasks, management commands, shell — `Event.objects` and `Order.objects` both count **0**. The ContextVar's `DenyAll()` default means forgetting to set a scope denies rather than leaks. |
| `test_deny_all_scope_denies` | Explicit `DenyAll` likewise yields 0 from both managers. |
| `test_owner_scope_never_returns_tenant_rows` | An `OwnerScope` for a user who genuinely created a **tenant-owned** row still gets 0. This is the `client_id__isnull=True` conjunct: a wrong or tampered owner value cannot reach across a tenant edge. |
| `test_order_owner_scope_traverses_event` | `Order` has no `created_by` of its own and must resolve through `event__created_by_id`. Without the per-model `owner_path`, a shared `created_by_id` filter raises `FieldError` and 500s every independent's order list. |

### `TenantlessPrivilegedCreationTests` (3)

The counterpart to the independent-customer path: a tenantless Master or
superuser must **not** create events. The row would land in the independent
space (`client = NULL`, `created_by` = them), which their own `DenyAll` scope
could never read back — an orphan visible to nobody.

| Test | Asserts |
|---|---|
| `test_tenantless_master_cannot_create_event` | Tenantless Master POST → **403**, and `Event.unscoped.count()` is unchanged. |
| `test_superuser_cannot_create_event` | Superuser POST → **403**, count unchanged. |
| `test_no_orphan_order_is_left_behind` | No `Order` row is created either — the rejection happens before the event/order pair is written. |

### `OrderSubmitTests` (11)

Requirement 3, reworked after code review. The original implementation
dispatched the notification from `perform_create`, but lines are added
afterwards through a separate request — so every email shipped with zero lines
and rendered the template's `{% empty %}` branch. The trigger is now an explicit
`POST /events/{id}/submit/`, which is the point at which an order actually
exists to notify about.

Recipients come from `Tenant.order_notification_emails`, not from `role="Master"`
users — the schema allows zero, one or many Masters per tenant with no guarantee
their login email is the right business address.

| Test | Asserts |
|---|---|
| `test_creating_event_alone_sends_no_email` | Creating an Event opens an empty basket and notifies nobody. Directly pins the bug that shipped. |
| `test_submit_sends_email_with_the_actual_lines` | The **real** HTTP flow — create, add 3 × Camisa @ 2500, submit — produces one mail to both recipients containing `Camisa`, `x3`, a correct `75.00` total, and **not** the "Sin productos agregados" empty branch. The original test invoked the task by hand after adding lines, so it passed against broken behaviour; this one asserts on the mail the system really sends. |
| `test_submit_is_dispatched_asynchronously` | Patches `send_order_created_email.delay` and asserts it was called. Pins the async contract independently of `CELERY_TASK_ALWAYS_EAGER`, which would otherwise hide a regression to a blocking inline call. |
| `test_cannot_submit_empty_order` | Submitting with no lines → **400**, no mail. |
| `test_cannot_submit_twice` | Re-submitting → **400**, no second mail. Guards against duplicate notifications. |
| `test_lines_are_frozen_after_submit` | After submit, add/patch/delete on lines all → **400** and the stored qty is unchanged. Fulfilment cannot end up working from a different basket than the one emailed. |
| `test_other_tenant_cannot_submit` | A Master of another tenant submitting → **404**, no mail. |
| `test_no_email_when_tenant_has_no_recipients_configured` | Unconfigured tenant is a clean no-op: submit still returns 200. |
| `test_independent_customer_submit_sends_no_email` | An independent customer's order (`client IS NULL`) submits fine and sends nothing — there is no tenant to read a recipient list from. |
| `test_qty_patch_rejects_non_numeric_instead_of_500` | `qty` of `"abc"`, `[1]`, `None`, `0` each → **400**. Previously `int()` raised `ValueError`/`TypeError` and escaped as an unhandled 500. |
| `test_task_is_noop_for_missing_order` | Unknown order id logs and returns rather than spinning the retry loop. |

---

## `apps/events/tests.py`

### `OrderLineTests` (7)

The product picker: `OrderLine` rows attached to an Event, with price and name
snapshotted at add time so later catalog edits don't rewrite order history.
`setUp` creates a `Jacket` product with one `JKT-M` variant at 4500 cents and
authenticates as a tenant-A user.

| Test | Asserts |
|---|---|
| `test_add_line_creates_order_line` | POST a line → **201**; qty, `unit_price_cents_snapshot` (4500) and `product_name_snapshot` ("Jacket") are all captured on the line. |
| `test_repeated_add_line_increments_qty_instead_of_duplicating` | Adding the same variant twice → **200** and a single row with `qty = 2`. Uses `get_or_create`, so the picker is idempotent per variant. |
| `test_add_line_rejects_inactive_variant` | `variant.active = False` → **400**, and no line is created. |
| `test_add_line_rejects_discontinued_product` | `product.status = discontinued` → **400**. Availability is checked at both variant and product level. |
| `test_cannot_add_line_to_other_tenants_event` | A tenant-B user adding a line to a tenant-A event → **404**. Line endpoints inherit event scoping via `self.get_object()`. |
| `test_update_line_qty` | PATCH `qty = 5` → **200** and persisted. |
| `test_delete_line` | DELETE → **204** and the row is gone. |

---

## Known gaps

Honest inventory of what is *not* covered:

1. **Retry behaviour is untested.** `autoretry_for=(Exception,)` with 5 attempts
   and backoff is configured but never exercised — a broken template or SMTP
   failure would retry 5 times in production with nothing covering that path.
2. **`apps/users` has no test module.** Untested: `UserManagementSerializer`'s role-escalation guard
   (`validate_role` blocking non-superusers from assigning `Master`), email
   normalization on create/update, and `UserViewSet` queryset scoping.
3. **`apps/tenants` has no test module.** `TenantSerializer`'s nested writable
   `legal_representative` — atomic create/update, the `_UNSET` sentinel that
   distinguishes PATCH-absent from explicit null, and the `get_fields()`
   `UniqueValidator` instance injection — is entirely unexercised despite being
   the most intricate serializer in the codebase.
4. **`apps/catalog` has no test module.** Soft-delete (`archived_at` +
   `NotArchivedManager` / `all_objects`) and S3 presigned-URL serving are
   untested.
5. **`OrderLine` has no scoped manager of its own.** It carries no `client` and
   is safe today only because both view paths derive the event from a scoped
   `self.get_object()`. Nothing asserts that invariant, so a future view that
   queries `OrderLine.objects.filter(event_id=...)` with a caller-supplied id
   would leak silently.
6. **No concurrency test** on `add_line`'s `get_or_create` — two simultaneous
   adds of the same variant could race.

## Note on version control

`.gitignore` contains a blanket `*.md`, so this file is **not tracked by
default**. Commit it with `git add -f TEST_SUITE.md` if it should live in the
repo.
