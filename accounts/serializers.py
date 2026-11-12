from payments.serializers import StrictSerializer
from rest_framework import serializers


class LoginSerializer(StrictSerializer):
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(max_length=256, trim_whitespace=False, write_only=True)
