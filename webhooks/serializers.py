from rest_framework import serializers

from payments.serializers import StrictSerializer
from .validators import validate_webhook_url


class WebhookEndpointCreateSerializer(StrictSerializer):
    url = serializers.URLField(max_length=2048)
    subscribed_events = serializers.ListField(child=serializers.ChoiceField(choices=["payment_intent.created", "payment_intent.canceled", "payment_intent.succeeded"]), min_length=1, max_length=10)

    def validate_url(self, value):
        try:
            validate_webhook_url(value)
        except Exception as error:
            raise serializers.ValidationError(str(error))
        return value
