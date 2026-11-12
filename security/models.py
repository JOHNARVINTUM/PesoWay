from django.db import models
from merchants.models import APIKey, Merchant


class RateLimitCounter(models.Model):
    """Database-backed fixed-window counter; updates are serialized per key."""
    subject = models.CharField(max_length=80)
    action = models.CharField(max_length=80)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["subject", "action", "window_start"], name="rate_limit_window_unique"),
            models.CheckConstraint(condition=models.Q(count__gte=0), name="rate_limit_count_nonnegative"),
        ]
        indexes = [models.Index(fields=["subject", "action", "window_start"])]


class SecurityAuditLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=80)
    outcome = models.CharField(max_length=24)
    merchant = models.ForeignKey(Merchant, null=True, blank=True, on_delete=models.PROTECT, related_name="security_audit_logs")
    api_key = models.ForeignKey(APIKey, null=True, blank=True, on_delete=models.SET_NULL, related_name="security_audit_logs")
    request_id = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [models.Index(fields=["merchant", "created_at"]), models.Index(fields=["action", "created_at"])]
