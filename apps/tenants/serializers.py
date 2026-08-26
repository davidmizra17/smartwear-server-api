from django.db import transaction
from rest_framework import serializers

from apps.tenants.models import Tenant
from apps.users.models import LegalRepresentative
from apps.users.serializers import LegalRepresentativeSerializer

_UNSET = object()


class TenantSerializer(serializers.ModelSerializer):
    legal_representative = LegalRepresentativeSerializer(required=False, allow_null=True)
    order_notification_emails = serializers.ListField(
        child=serializers.EmailField(), required=False, allow_empty=True
    )

    class Meta:
        model = Tenant
        fields = ["id", "name", "document_id_number", "legal_representative", "order_notification_emails"]
        read_only_fields = ["id"]

    def get_fields(self):
        fields = super().get_fields()
        # Inject the existing LegalRepresentative instance so DRF's UniqueValidator
        # on email excludes the current record during updates (PATCH/PUT).
        if self.instance and self.instance.legal_representative:
            fields["legal_representative"].instance = self.instance.legal_representative
        return fields

    def create(self, validated_data):
        legal_rep_data = validated_data.pop("legal_representative", None)
        with transaction.atomic():
            legal_rep = LegalRepresentative.objects.create(**legal_rep_data) if legal_rep_data else None
            return Tenant.objects.create(legal_representative=legal_rep, **validated_data)

    def update(self, instance, validated_data):
        # Use sentinel to distinguish "key absent" (do nothing) from "key=null" (clear link).
        legal_rep_data = validated_data.pop("legal_representative", _UNSET)
        with transaction.atomic():
            if legal_rep_data is not _UNSET:
                if legal_rep_data is None:
                    instance.legal_representative = None
                elif instance.legal_representative_id:
                    for attr, value in legal_rep_data.items():
                        setattr(instance.legal_representative, attr, value)
                    instance.legal_representative.save()
                else:
                    instance.legal_representative = LegalRepresentative.objects.create(**legal_rep_data)
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
        return instance

class TenantListSerializer(serializers.ModelSerializer):
    legal_representative = LegalRepresentativeSerializer(allow_null=True)

    class Meta:
        model = Tenant
        fields = ["id", "name", "document_id_number", "legal_representative", "order_notification_emails"]
