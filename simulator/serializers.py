from rest_framework import serializers

from payments.serializers import StrictSerializer


class SimulatedAttemptCreateSerializer(StrictSerializer):
    method = serializers.ChoiceField(choices=["gcash", "maya", "card", "qrph"])


class SimulatedCompletionSerializer(StrictSerializer):
    # The scenario is accepted only by the explicitly scoped simulation endpoint.
    scenario = serializers.ChoiceField(choices=["succeeded", "failed", "canceled"])
