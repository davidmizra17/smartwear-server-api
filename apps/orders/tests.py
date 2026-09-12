import uuid
from unittest import mock

from django.core import mail
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.catalog.models import Product as CatalogProduct, Variant
from apps.events.models import Event, OrderLine
from apps.orders.models import Order
from apps.orders.tasks import send_order_created_email
from apps.tenants.models import Tenant
from apps.tenants.scope import (
    DenyAll,
    OwnerScope,
    TenantScope,
    reset_current_scope,
    scope_for_user,
    set_current_scope,
)
from apps.users.models import User


class OrderTestsBase(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(id=uuid.uuid4(), name="Client A")
        self.tenant_b = Tenant.objects.create(id=uuid.uuid4(), name="Client B")

        self.operator_a = User.objects.create_user(
            email="operator-a@test.com", tenant=self.tenant_a, password="pass1234", role="Operator"
        )
        self.master_a = User.objects.create_user(
            email="master-a@test.com", tenant=self.tenant_a, password="pass1234", role="Master"
        )
        self.master_b = User.objects.create_user(
            email="master-b@test.com", tenant=self.tenant_b, password="pass1234", role="Master"
        )

        self.event_a = Event.objects.create(
            id=uuid.uuid4(),
            client=self.tenant_a,
            created_by=self.operator_a,
            title="Evento A",
            event_date="2026-09-01",
        )
        self.order_a = Order.unscoped.create(id=uuid.uuid4(), event=self.event_a, client=self.tenant_a)

        event_b = Event.objects.create(
            id=uuid.uuid4(),
            client=self.tenant_b,
            created_by=self.master_b,
            title="Evento B",
            event_date="2026-09-02",
        )
        self.order_b = Order.unscoped.create(id=uuid.uuid4(), event=event_b, client=self.tenant_b)

        self.api = APIClient()

    def _auth(self, email, password):
        res = self.api.post("/api/v1/auth/token/", {"email": email, "password": password})
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")


class TenantIsolationTests(OrderTestsBase):
    def test_user_a_cannot_see_user_b_orders(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        ids = [o["id"] for o in res.data["results"]]
        self.assertIn(str(self.order_a.id), ids)
        self.assertNotIn(str(self.order_b.id), ids)

    def test_user_cannot_fetch_other_tenant_order_detail(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.get(f"/api/v1/orders/{self.order_b.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_master_cannot_change_status_of_other_tenant_order(self):
        self._auth("master-b@test.com", "pass1234")
        res = self.api.patch(
            f"/api/v1/orders/{self.order_a.id}/status/", {"status": Order.STATUS_ORDERED}
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


class AuthTests(OrderTestsBase):
    def test_unauthenticated_request_rejected(self):
        res = self.api.get("/api/v1/orders/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class ReadAccessTests(OrderTestsBase):
    def test_operator_can_list_own_tenant_orders(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)
        self.assertEqual(res.data["results"][0]["status"], Order.STATUS_PENDING)

    def test_order_detail_includes_event_summary(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.get(f"/api/v1/orders/{self.order_a.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["event_title"], "Evento A")


class StatusWritePermissionTests(OrderTestsBase):
    def test_operator_cannot_change_status(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.patch(
            f"/api/v1/orders/{self.order_a.id}/status/", {"status": Order.STATUS_ORDERED}
        )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.order_a.refresh_from_db()
        self.assertEqual(self.order_a.status, Order.STATUS_PENDING)

    def test_master_can_change_status_of_same_tenant_order(self):
        self._auth("master-a@test.com", "pass1234")
        res = self.api.patch(
            f"/api/v1/orders/{self.order_a.id}/status/", {"status": Order.STATUS_ORDERED}
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.order_a.refresh_from_db()
        self.assertEqual(self.order_a.status, Order.STATUS_ORDERED)

    def test_operator_cannot_use_put_on_base_order_endpoint(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.put(f"/api/v1/orders/{self.order_a.id}/", {"status": Order.STATUS_ORDERED})
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_delete_not_allowed(self):
        self._auth("master-a@test.com", "pass1234")
        res = self.api.delete(f"/api/v1/orders/{self.order_a.id}/")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


class EventCreationAutoCreatesOrderTests(OrderTestsBase):
    def test_creating_event_auto_creates_order(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.post(
            "/api/v1/events/",
            {"title": "Nuevo evento", "event_date": "2026-09-10"},
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        event_id = res.data["id"]
        order = Order.unscoped.get(event_id=event_id)
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertEqual(order.client_id, self.tenant_a.id)

    def test_event_serializer_does_not_expose_status(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.get(f"/api/v1/events/{self.event_a.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotIn("status", res.data)


class IndependentCustomerTests(OrderTestsBase):
    """
    Independent customers are users with no tenant who act on their own
    behalf. Their rows carry client=NULL and are scoped by created_by.
    """

    def setUp(self):
        super().setUp()
        self.independent = User.objects.create_user(
            email="independent@test.com", tenant=None, password="pass1234", role="Operator"
        )
        self.other_independent = User.objects.create_user(
            email="independent-2@test.com", tenant=None, password="pass1234", role="Operator"
        )
        self.independent_event = Event.unscoped.create(
            id=uuid.uuid4(),
            client=None,
            created_by=self.independent,
            title="Evento Independiente",
            event_date="2026-09-03",
        )
        self.independent_order = Order.unscoped.create(
            id=uuid.uuid4(), event=self.independent_event, client=None
        )

    def test_independent_can_create_event_and_order(self):
        self._auth("independent@test.com", "pass1234")
        res = self.api.post(
            "/api/v1/events/",
            {"title": "Pedido propio", "event_date": "2026-09-11"},
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        order = Order.unscoped.get(event_id=res.data["id"])
        self.assertIsNone(order.client_id)

    def test_independent_sees_own_orders(self):
        self._auth("independent@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        ids = [o["id"] for o in res.data["results"]]
        self.assertEqual(ids, [str(self.independent_order.id)])

    def test_independent_cannot_see_other_independents_orders(self):
        self._auth("independent-2@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        ids = [o["id"] for o in res.data["results"]]
        self.assertNotIn(str(self.independent_order.id), ids)

    def test_independent_cannot_see_tenant_orders(self):
        self._auth("independent@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        ids = [o["id"] for o in res.data["results"]]
        self.assertNotIn(str(self.order_a.id), ids)
        self.assertNotIn(str(self.order_b.id), ids)

    def test_tenant_operator_cannot_see_independent_orders(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        ids = [o["id"] for o in res.data["results"]]
        self.assertNotIn(str(self.independent_order.id), ids)

    def test_independent_cannot_fetch_tenant_order_detail(self):
        self._auth("independent@test.com", "pass1234")
        res = self.api.get(f"/api/v1/orders/{self.order_a.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_independent_sees_own_events_only(self):
        self._auth("independent@test.com", "pass1234")
        res = self.api.get("/api/v1/events/")
        ids = [e["id"] for e in res.data["results"]]
        self.assertEqual(ids, [str(self.independent_event.id)])


class ScopeResolutionTests(TestCase):
    """
    Unit-level guards on the scope <-> manager contract. These assert the
    fail-closed structure directly, without going through a request.
    """

    def setUp(self):
        self.tenant = Tenant.objects.create(id=uuid.uuid4(), name="Client S")
        self.operator = User.objects.create_user(
            email="op@test.com", tenant=self.tenant, password="pass1234", role="Operator"
        )
        self.tenantless_master = User.objects.create_user(
            email="master-none@test.com", tenant=None, password="pass1234", role="Master"
        )
        self.tenant_master = User.objects.create_user(
            email="master-with@test.com", tenant=self.tenant, password="pass1234", role="Master"
        )
        self.independent = User.objects.create_user(
            email="indep@test.com", tenant=None, password="pass1234", role="Operator"
        )
        self.superuser = User.objects.create_superuser(email="root@test.com", password="pass1234")

        self.event = Event.unscoped.create(
            id=uuid.uuid4(),
            client=self.tenant,
            created_by=self.operator,
            title="Evento S",
            event_date="2026-09-04",
        )
        self.order = Order.unscoped.create(id=uuid.uuid4(), event=self.event, client=self.tenant)

    def test_tenant_master_stays_tenant_scoped(self):
        # Regression guard: Masters may hold a tenant, and when they do they
        # must keep seeing that tenant's rows. Resolving role before tenant
        # would silently blank them out.
        self.assertEqual(scope_for_user(self.tenant_master), TenantScope(self.tenant.id))

    def test_tenantless_master_and_superuser_deny(self):
        self.assertEqual(scope_for_user(self.tenantless_master), DenyAll())
        self.assertEqual(scope_for_user(self.superuser), DenyAll())

    def test_independent_resolves_to_owner_scope(self):
        self.assertEqual(scope_for_user(self.independent), OwnerScope(self.independent.pk))

    def test_no_scope_context_denies(self):
        # Celery tasks, management commands, anything that never authenticated.
        self.assertEqual(Event.objects.count(), 0)
        self.assertEqual(Order.objects.count(), 0)

    def test_deny_all_scope_denies(self):
        token = set_current_scope(DenyAll())
        try:
            self.assertEqual(Event.objects.count(), 0)
            self.assertEqual(Order.objects.count(), 0)
        finally:
            reset_current_scope(token)

    def test_owner_scope_never_returns_tenant_rows(self):
        # Even though self.operator created this tenant-owned event, an
        # OwnerScope for them must not surface it: client_id is not NULL.
        token = set_current_scope(OwnerScope(self.operator.pk))
        try:
            self.assertEqual(Event.objects.count(), 0)
            self.assertEqual(Order.objects.count(), 0)
        finally:
            reset_current_scope(token)

    def test_order_owner_scope_traverses_event(self):
        # Order has no created_by of its own; it must resolve through Event
        # rather than raising FieldError.
        independent_event = Event.unscoped.create(
            id=uuid.uuid4(),
            client=None,
            created_by=self.independent,
            title="Evento indep",
            event_date="2026-09-05",
        )
        independent_order = Order.unscoped.create(
            id=uuid.uuid4(), event=independent_event, client=None
        )
        token = set_current_scope(OwnerScope(self.independent.pk))
        try:
            self.assertEqual(list(Order.objects.values_list("id", flat=True)), [independent_order.id])
        finally:
            reset_current_scope(token)


class TenantlessPrivilegedCreationTests(OrderTestsBase):
    """
    A tenantless Master or superuser must not create events: the row would land
    in the independent space (client=NULL, created_by=them), which their own
    DenyAll scope can never read back.
    """

    def setUp(self):
        super().setUp()
        self.tenantless_master = User.objects.create_user(
            email="master-none@test.com", tenant=None, password="pass1234", role="Master"
        )
        self.superuser = User.objects.create_superuser(email="root@test.com", password="pass1234")

    def _post_event(self):
        return self.api.post(
            "/api/v1/events/",
            {"title": "Huerfano", "event_date": "2026-09-12"},
        )

    def test_tenantless_master_cannot_create_event(self):
        self._auth("master-none@test.com", "pass1234")
        before = Event.unscoped.count()
        res = self._post_event()
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Event.unscoped.count(), before)

    def test_superuser_cannot_create_event(self):
        self._auth("root@test.com", "pass1234")
        before = Event.unscoped.count()
        res = self._post_event()
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(Event.unscoped.count(), before)

    def test_no_orphan_order_is_left_behind(self):
        self._auth("master-none@test.com", "pass1234")
        before = Order.unscoped.count()
        self._post_event()
        self.assertEqual(Order.unscoped.count(), before)


class OrderSubmitTests(OrderTestsBase):
    """
    Submitting is the point at which an order exists to be notified about.
    Creating an Event only opens an empty basket.
    """

    def setUp(self):
        super().setUp()
        self.tenant_a.order_notification_emails = ["ops@clientea.com", "admin@clientea.com"]
        self.tenant_a.save()
        self.product = CatalogProduct.objects.create(name="Camisa")
        self.variant = Variant.objects.create(
            product=self.product, sku="CAM-L", size="L", price_cents=2500, currency="USD"
        )
        mail.outbox = []

    def _new_event(self, title="Evento con correo"):
        return self.api.post(
            "/api/v1/events/", {"title": title, "event_date": "2026-09-15"}
        ).data["id"]

    def _add_line(self, event_id, qty=3):
        return self.api.post(
            f"/api/v1/events/{event_id}/lines/",
            {"variant_id": str(self.variant.id), "qty": qty},
            format="json",
        )

    def _submit(self, event_id):
        return self.api.post(f"/api/v1/events/{event_id}/submit/")

    def test_creating_event_alone_sends_no_email(self):
        self._auth("operator-a@test.com", "pass1234")
        self._new_event()
        self.assertEqual(mail.outbox, [])

    def test_submit_sends_email_with_the_actual_lines(self):
        # The whole point: assert on the mail the system really sends, through
        # the real HTTP flow, not by invoking the task by hand.
        self._auth("operator-a@test.com", "pass1234")
        event_id = self._new_event()
        self._add_line(event_id, qty=3)
        res = self._submit(event_id)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["status"], Order.STATUS_SUBMITTED)
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, ["ops@clientea.com", "admin@clientea.com"])
        self.assertIn("Evento con correo", message.subject)
        self.assertIn("Camisa", message.body)
        self.assertIn("x3", message.body)
        self.assertIn("75.00", message.body)
        self.assertNotIn("Sin productos agregados", message.body)

    def test_submit_is_dispatched_asynchronously(self):
        # Pins the async contract independently of CELERY_TASK_ALWAYS_EAGER,
        # which would otherwise hide a regression to a blocking inline call.
        self._auth("operator-a@test.com", "pass1234")
        event_id = self._new_event()
        self._add_line(event_id)
        with mock.patch("apps.events.views.send_order_created_email.delay") as delayed:
            self._submit(event_id)
        delayed.assert_called_once()

    def test_cannot_submit_empty_order(self):
        self._auth("operator-a@test.com", "pass1234")
        event_id = self._new_event()
        res = self._submit(event_id)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mail.outbox, [])

    def test_cannot_submit_twice(self):
        self._auth("operator-a@test.com", "pass1234")
        event_id = self._new_event()
        self._add_line(event_id)
        self._submit(event_id)
        mail.outbox = []
        res = self._submit(event_id)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(mail.outbox, [])

    def test_lines_are_frozen_after_submit(self):
        self._auth("operator-a@test.com", "pass1234")
        event_id = self._new_event()
        self._add_line(event_id)
        line_id = OrderLine.objects.get(event_id=event_id).id
        self._submit(event_id)

        self.assertEqual(self._add_line(event_id).status_code, status.HTTP_400_BAD_REQUEST)
        patched = self.api.patch(
            f"/api/v1/events/{event_id}/lines/{line_id}/", {"qty": 9}, format="json"
        )
        self.assertEqual(patched.status_code, status.HTTP_400_BAD_REQUEST)
        deleted = self.api.delete(f"/api/v1/events/{event_id}/lines/{line_id}/")
        self.assertEqual(deleted.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrderLine.objects.get(event_id=event_id).qty, 3)

    def test_other_tenant_cannot_submit(self):
        self._auth("operator-a@test.com", "pass1234")
        event_id = self._new_event()
        self._add_line(event_id)
        mail.outbox = []
        self._auth("master-b@test.com", "pass1234")
        self.assertEqual(self._submit(event_id).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(mail.outbox, [])

    def test_no_email_when_tenant_has_no_recipients_configured(self):
        self.tenant_a.order_notification_emails = []
        self.tenant_a.save()
        self._auth("operator-a@test.com", "pass1234")
        event_id = self._new_event()
        self._add_line(event_id)
        res = self._submit(event_id)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mail.outbox, [])

    def test_independent_customer_submit_sends_no_email(self):
        User.objects.create_user(
            email="indep-mail@test.com", tenant=None, password="pass1234", role="Operator"
        )
        self._auth("indep-mail@test.com", "pass1234")
        event_id = self._new_event()
        self._add_line(event_id)
        res = self._submit(event_id)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(mail.outbox, [])

    def test_qty_patch_rejects_non_numeric_instead_of_500(self):
        self._auth("operator-a@test.com", "pass1234")
        event_id = self._new_event()
        self._add_line(event_id)
        line_id = OrderLine.objects.get(event_id=event_id).id
        for bad in ("abc", [1], None, 0):
            res = self.api.patch(
                f"/api/v1/events/{event_id}/lines/{line_id}/", {"qty": bad}, format="json"
            )
            self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, msg=f"qty={bad!r}")

    def test_task_is_noop_for_missing_order(self):
        send_order_created_email(str(uuid.uuid4()))
        self.assertEqual(mail.outbox, [])
