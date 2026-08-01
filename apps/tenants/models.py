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

    class Meta:
        db_table = "client"

    def __str__(self):
        return self.name
