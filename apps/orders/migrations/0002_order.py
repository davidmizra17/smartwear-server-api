import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
        ("tenants", "0003_tenant_document_id_number_and_more"),
        ("events", "0002_orderline"),
    ]

    operations = [
        # The legacy `order` table (CSV inventory-import pipeline, being
        # deprecated) is dropped here rather than migrated: its schema
        # (unique raw_nombre, no status, one-product-per-row) cannot
        # represent an Event-derived customer order, and the client
        # confirmed its existing contents are no longer needed.
        migrations.RunSQL(
            sql='DROP TABLE IF EXISTS "order";',
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                (
                    "status",
                    models.CharField(
                        choices=[("pending", "Pending"), ("ordered", "Ordered"), ("cancelled", "Cancelled")],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "client",
                    models.ForeignKey(
                        db_constraint=False,
                        on_delete=django.db.models.deletion.DO_NOTHING,
                        related_name="orders",
                        to="tenants.tenant",
                    ),
                ),
                (
                    "event",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="order",
                        to="events.event",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
