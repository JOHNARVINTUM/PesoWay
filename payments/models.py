import uuid

from django.db import models
from django.utils import timezone

from merchants.models import Application, Merchant


class PaymentIntent(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        REQUIRES_PAYMENT_METHOD = "requires_payment_method", "Requires payment method"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"
        EXPIRED = "expired", "Expired"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="payment_intents")
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="payment_intents")
    amount_centavos = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="PHP")
    merchant_reference = models.CharField(max_length=100)
    description = models.CharField(max_length=500, blank=True)
    return_url = models.URLField(max_length=2048, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.CREATED)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_centavos__gt=0), name="payment_intent_amount_positive"),
            models.CheckConstraint(condition=models.Q(currency="PHP"), name="payment_intent_php_only"),
            models.UniqueConstraint(fields=["merchant", "merchant_reference"], name="merchant_payment_reference_unique"),
        ]
        indexes = [models.Index(fields=["merchant", "public_id"]), models.Index(fields=["merchant", "created_at"]), models.Index(fields=["status", "expires_at"])]

    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()


class PaymentAttempt(models.Model):
    class Method(models.TextChoices):
        GCASH = "gcash", "Simulated GCash"
        MAYA = "maya", "Simulated Maya"
        CARD = "card", "Simulated Card"
        QRPH = "qrph", "Simulated QR Ph"

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    intent = models.ForeignKey(PaymentIntent, on_delete=models.PROTECT, related_name="attempts")
    method = models.CharField(max_length=16, choices=Method.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.CREATED)
    reference = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)


class IdempotencyRecord(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="idempotency_records")
    operation = models.CharField(max_length=64)
    key = models.CharField(max_length=255)
    request_fingerprint = models.CharField(max_length=64)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    response_body = models.JSONField(null=True, blank=True)
    payment_intent = models.ForeignKey(PaymentIntent, on_delete=models.PROTECT, null=True, blank=True, related_name="idempotency_records")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["merchant", "operation", "key"], name="merchant_idempotency_key_unique")]
        indexes = [models.Index(fields=["merchant", "operation", "created_at"])]
