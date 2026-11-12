import uuid

from django.core.exceptions import ValidationError
from django.db import models

from merchants.models import Merchant
from payments.models import PaymentIntent


class LedgerEntry(models.Model):
    """Append-only merchant financial audit record. Amounts are always centavos."""
    class EntryType(models.TextChoices):
        PAYMENT_CREATED = "payment_created", "Payment created"
        PAYMENT_SUCCEEDED = "payment_succeeded", "Payment succeeded"
        PAYMENT_CANCELED = "payment_canceled", "Payment canceled"
        REFUND = "refund", "Refund"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="ledger_entries")
    payment_intent = models.ForeignKey(PaymentIntent, null=True, blank=True, on_delete=models.PROTECT, related_name="ledger_entries")
    entry_type = models.CharField(max_length=32, choices=EntryType.choices)
    amount_centavos = models.BigIntegerField()
    currency = models.CharField(max_length=3, default="PHP")
    reference = models.CharField(max_length=100, unique=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=models.Q(currency="PHP"), name="ledger_php_only")]
        indexes = [models.Index(fields=["merchant", "created_at"]), models.Index(fields=["payment_intent", "created_at"])]

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Ledger entries are immutable; add a correcting entry instead.")
        return super().save(*args, **kwargs)


class Refund(models.Model):
    class Status(models.TextChoices):
        SUCCEEDED = "succeeded", "Simulated succeeded"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="refunds")
    payment_intent = models.ForeignKey(PaymentIntent, on_delete=models.PROTECT, related_name="refunds")
    amount_centavos = models.PositiveBigIntegerField()
    currency = models.CharField(max_length=3, default="PHP")
    merchant_reference = models.CharField(max_length=100)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.SUCCEEDED)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(amount_centavos__gt=0), name="refund_amount_positive"),
            models.UniqueConstraint(fields=["merchant", "merchant_reference"], name="merchant_refund_reference_unique"),
        ]
        indexes = [models.Index(fields=["merchant", "created_at"]), models.Index(fields=["payment_intent", "created_at"])]
