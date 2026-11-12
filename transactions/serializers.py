import re
from rest_framework import serializers

from payments.serializers import StrictSerializer
from .models import LedgerEntry, Refund


class RefundCreateSerializer(StrictSerializer):
    payment_intent_id = serializers.UUIDField()
    amount_centavos = serializers.IntegerField(min_value=1, max_value=100_000_000_000)
    merchant_reference = serializers.RegexField(regex=re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,99}$"), max_length=100)


class LedgerEntrySerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = LedgerEntry
        fields = ["id", "entry_type", "amount_centavos", "currency", "reference", "created_at", "payment_intent"]


class RefundSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField(source="public_id", read_only=True)

    class Meta:
        model = Refund
        fields = ["id", "amount_centavos", "currency", "merchant_reference", "status", "created_at"]
