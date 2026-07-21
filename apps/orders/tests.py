import uuid
from datetime import datetime, timezone

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.orders.models import Order, Product
from apps.tenants.models import Tenant
from apps.users.models import User


def make_order(product, tenant, suffix):
    return Order.unscoped.create(
        id=uuid.uuid4(),
        product=product,
        client=tenant,
        unit_cost="10.00",
        quantity=2,
        inventory_value="20.00",
        raw_nombre=f"order-{suffix}",
        source_file=f"file_{suffix}.csv",
        uploaded_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TenantIsolationTests(TestCase):
    def setUp(self):
        self.tenant_a = Tenant.objects.create(id=uuid.uuid4(), name="Client A")
        self.tenant_b = Tenant.objects.create(id=uuid.uuid4(), name="Client B")

        self.product = Product.objects.create(id=uuid.uuid4(), name="Widget", sku="W-001")

        self.user_a = User.objects.create_user(email="a@test.com", tenant=self.tenant_a, password="pass1234")
        self.user_b = User.objects.create_user(email="b@test.com", tenant=self.tenant_b, password="pass1234")

        self.order_a = make_order(self.product, self.tenant_a, "a")
        self.order_b = make_order(self.product, self.tenant_b, "b")

        self.api = APIClient()

    def _auth(self, email, password):
        res = self.api.post("/api/v1/auth/token/", {"email": email, "password": password})
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

    # --- isolation ---

    def test_user_a_cannot_see_user_b_orders(self):
        self._auth("a@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        ids = [o["id"] for o in res.data["results"]]
        self.assertIn(str(self.order_a.id), ids)
        self.assertNotIn(str(self.order_b.id), ids)

    def test_user_b_cannot_see_user_a_orders(self):
        self._auth("b@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        ids = [o["id"] for o in res.data["results"]]
        self.assertIn(str(self.order_b.id), ids)
        self.assertNotIn(str(self.order_a.id), ids)

    def test_user_cannot_fetch_other_tenant_order_detail(self):
        self._auth("a@test.com", "pass1234")
        res = self.api.get(f"/api/v1/orders/{self.order_b.id}/")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # --- auth ---

    def test_unauthenticated_request_rejected(self):
        res = self.api.get("/api/v1/orders/")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # --- happy path ---

    def test_authenticated_user_sees_own_orders(self):
        self._auth("a@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

    def test_order_detail_returns_correct_order(self):
        self._auth("a@test.com", "pass1234")
        res = self.api.get(f"/api/v1/orders/{self.order_a.id}/")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], str(self.order_a.id))

    # --- filters ---

    def test_filter_by_source_file(self):
        self._auth("a@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/?source_file=file_a")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

    def test_filter_by_product_name(self):
        self._auth("a@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/?product_name=widget")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 1)

    def test_filter_excludes_non_matching_source_file(self):
        self._auth("a@test.com", "pass1234")
        res = self.api.get("/api/v1/orders/?source_file=file_b")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["count"], 0)
