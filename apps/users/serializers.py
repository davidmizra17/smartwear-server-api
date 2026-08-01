from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.users.models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "role", "date_joined"]
        read_only_fields = fields


class UserManagementSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "tenant", "role", "is_active", "password", "date_joined"]
        read_only_fields = ["id", "date_joined"]

    def validate_role(self, value):
        request = self.context.get("request")
        if value == "Master" and not (request and request.user.is_superuser):
            raise serializers.ValidationError("Only superusers can assign the Master role.")
        return value

    def create(self, validated_data):
        password = validated_data.pop("password")
        validated_data["email"] = User.objects.normalize_email(validated_data["email"])
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        if "email" in validated_data:
            validated_data["email"] = User.objects.normalize_email(validated_data["email"])
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class TenantTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["tenant_id"] = str(user.tenant_id) if user.tenant_id else None
        token["email"] = user.email
        token["role"] = user.role
        return token
