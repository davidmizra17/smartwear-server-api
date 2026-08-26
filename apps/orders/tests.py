import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.events.models import Event
from apps.orders.models import Order
from apps.tenants.models import Tenant
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
        res = self.api.patch(f"/api/v1/orders/{self.order_a.id}/", {"status": Order.STATUS_ORDERED})
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
        res = self.api.patch(f"/api/v1/orders/{self.order_a.id}/", {"status": Order.STATUS_ORDERED})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.order_a.refresh_from_db()
        self.assertEqual(self.order_a.status, Order.STATUS_PENDING)

    def test_master_can_change_status_of_same_tenant_order(self):
        self._auth("master-a@test.com", "pass1234")
        res = self.api.patch(f"/api/v1/orders/{self.order_a.id}/", {"status": Order.STATUS_ORDERED})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.order_a.refresh_from_db()
        self.assertEqual(self.order_a.status, Order.STATUS_ORDERED)

    def test_operator_cannot_use_put(self):
        self._auth("operator-a@test.com", "pass1234")
        res = self.api.put(f"/api/v1/orders/{self.order_a.id}/", {"status": Order.STATUS_ORDERED})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

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

