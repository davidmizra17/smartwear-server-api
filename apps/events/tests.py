import uuid

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.catalog.models import Product, Variant
from apps.events.models import Event, OrderLine
from apps.orders.models import Order
from apps.tenants.models import Tenant
from apps.users.models import User


class OrderLineTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(id=uuid.uuid4(), name="Client A")
        self.other_tenant = Tenant.objects.create(id=uuid.uuid4(), name="Client B")
        self.user = User.objects.create_user(email="a@test.com", tenant=self.tenant, password="pass1234")
        self.other_user = User.objects.create_user(email="b@test.com", tenant=self.other_tenant, password="pass1234")

        self.product = Product.objects.create(name="Jacket")
        self.variant = Variant.objects.create(
            product=self.product, sku="JKT-M", size="M", price_cents=4500, currency="USD"
        )

        self.api = APIClient()
        res = self.api.post("/api/v1/auth/token/", {"email": "a@test.com", "password": "pass1234"})
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")

        self.event = Event.objects.create(client=self.tenant, created_by=self.user, title="Order", event_date="2026-08-20")
        self.order = Order.unscoped.create(event=self.event, client=self.tenant)

    def _add_line(self, qty=1, variant_id=None):
        return self.api.post(
            f"/api/v1/events/{self.event.id}/lines/",
            {"variant_id": str(variant_id or self.variant.id), "qty": qty},
            format="json",
        )

    def test_add_line_creates_order_line(self):
        res = self._add_line(qty=2)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(OrderLine.objects.count(), 1)
        line = OrderLine.objects.get()
        self.assertEqual(line.qty, 2)
        self.assertEqual(line.unit_price_cents_snapshot, 4500)
        self.assertEqual(line.product_name_snapshot, "Jacket")

    def test_repeated_add_line_increments_qty_instead_of_duplicating(self):
        self._add_line(qty=1)
        res = self._add_line(qty=1)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(OrderLine.objects.count(), 1)
        self.assertEqual(OrderLine.objects.get().qty, 2)

    def test_add_line_rejects_inactive_variant(self):
        self.variant.active = False
        self.variant.save()
        res = self._add_line()
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(OrderLine.objects.count(), 0)

    def test_add_line_rejects_discontinued_product(self):
        self.product.status = Product.STATUS_DISCONTINUED
        self.product.save()
        res = self._add_line()
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cannot_add_line_to_other_tenants_event(self):
        api = APIClient()
        res = api.post("/api/v1/auth/token/", {"email": "b@test.com", "password": "pass1234"})
        api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        res = api.post(
            f"/api/v1/events/{self.event.id}/lines/",
            {"variant_id": str(self.variant.id), "qty": 1},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_update_line_qty(self):
        self._add_line(qty=1)
        line = OrderLine.objects.get()
        res = self.api.patch(f"/api/v1/events/{self.event.id}/lines/{line.id}/", {"qty": 5}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        line.refresh_from_db()
        self.assertEqual(line.qty, 5)

    def test_delete_line(self):
        self._add_line(qty=1)
        line = OrderLine.objects.get()
        res = self.api.delete(f"/api/v1/events/{self.event.id}/lines/{line.id}/")
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(OrderLine.objects.count(), 0)
