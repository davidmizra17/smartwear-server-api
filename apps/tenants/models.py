import uuid

from django.db import models


class Tenant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField(unique=True)

    class Meta:
        # Owned by the ingestion service — CRM reads only, never writes.
        managed = False
        db_table = "client"

    def __str__(self):
        return self.name
