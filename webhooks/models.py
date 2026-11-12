import secrets
import uuid

from django.db import models
from django.utils import timezone

from merchants.models import Merchant
from .crypto import encrypt_secret
from .validators import validate_webhook_url


class WebhookEndpoint(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="webhook_endpoints")
    url = models.URLField(max_length=2048, validators=[validate_webhook_url])
    encrypted_secret = models.TextField(editable=False)
    subscribed_events = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["merchant", "is_active"])]

    @classmethod
    def create_secret(cls, *, merchant, url: str, subscribed_events: list[str]):
        validate_webhook_url(url)
        secret = f"whsec_{secrets.token_urlsafe(32)}"
        endpoint = cls.objects.create(merchant=merchant, url=url, encrypted_secret=encrypt_secret(secret), subscribed_events=sorted(set(subscribed_events)))
        return endpoint, secret


class WebhookEvent(models.Model):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="webhook_events")
    event_type = models.CharField(max_length=80)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["merchant", "created_at"]), models.Index(fields=["event_type", "created_at"])]


class WebhookDelivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    endpoint = models.ForeignKey(WebhookEndpoint, on_delete=models.PROTECT, related_name="deliveries")
    event = models.ForeignKey(WebhookEvent, on_delete=models.PROTECT, related_name="deliveries")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    attempt_count = models.PositiveSmallIntegerField(default=0)
    next_attempt_at = models.DateTimeField(default=timezone.now)
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    last_error = models.CharField(max_length=256, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["endpoint", "event"], name="webhook_delivery_once")]
        indexes = [models.Index(fields=["status", "next_attempt_at"])]
