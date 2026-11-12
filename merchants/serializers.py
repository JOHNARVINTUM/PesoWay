from rest_framework import serializers

from payments.serializers import StrictSerializer


ALLOWED_SCOPES = {"payments:read", "payments:write", "simulator:write", "transactions:read", "refunds:write", "webhooks:read", "webhooks:write"}


class APIKeyCreateSerializer(StrictSerializer):
    application_id = serializers.IntegerField(min_value=1)
    scopes = serializers.ListField(child=serializers.ChoiceField(choices=sorted(ALLOWED_SCOPES)), min_length=1, max_length=len(ALLOWED_SCOPES))
