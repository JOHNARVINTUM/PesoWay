import re
from urllib.parse import urlparse
from django.conf import settings
from rest_framework import serializers

from .models import PaymentIntent


class StrictSerializer(serializers.Serializer):
    """DRF serializers normally ignore unknown JSON fields; financial APIs must not."""
    def to_internal_value(self, data):
        if isinstance(data, dict):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({field: ["Unknown field."] for field in sorted(unknown)})
        return super().to_internal_value(data)


class PaymentIntentCreateSerializer(StrictSerializer):
    amount_centavos = serializers.IntegerField(min_value=1, max_value=100_000_000_000)
    currency = serializers.ChoiceField(choices=["PHP"])
    merchant_reference = serializers.RegexField(regex=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$"), max_length=100)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    return_url = serializers.URLField(max_length=2048, required=False, allow_blank=True)
    expires_in_minutes = serializers.IntegerField(min_value=5, max_value=1440, required=False, default=30)

    def validate_return_url(self, value):
        if not value:
            return value
        parsed = urlparse(value)
        local = settings.DEBUG and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
        if (parsed.scheme != "https" and not local) or not parsed.hostname or parsed.username or parsed.password:
            raise serializers.ValidationError("Return URL must be HTTPS (or localhost HTTP in debug mode).")
        return value


class PaymentIntentSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)
    amount_centavos = serializers.IntegerField(read_only=True)

    class Meta:
        model = PaymentIntent
        fields = ["id", "amount_centavos", "currency", "merchant_reference", "description", "return_url", "status", "created_at", "expires_at", "completed_at"]
