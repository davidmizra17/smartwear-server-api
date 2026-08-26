import uuid

from django.db import models


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField(unique=True)
    document_id_number = models.CharField(max_length=100, blank=True)
    legal_representative = models.OneToOneField(
        "users.LegalRepresentative",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant",
    )

    # Recipients for order-created notifications. Configured per tenant rather
    # than derived from role="Master" users: the schema allows zero, one or many
    # Masters per tenant, with no guarantee their login email is the right
    # business address. JSONField (not ArrayField) because tests run on SQLite.
    # db_default is deliberate, not redundant with default: the `client` table
    # is co-owned by the ingestion service, which inserts rows without knowing
    # about this column. A Django-only default would drop the DB default and
    # make those inserts fail on NOT NULL.
    order_notification_emails = models.JSONField(default=list, db_default=[], blank=True)

    class Meta:
        db_table = "client"

    def __str__(self):
        return self.name
