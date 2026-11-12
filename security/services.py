from datetime import datetime, timezone as datetime_timezone

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled

from .models import RateLimitCounter, SecurityAuditLog


def enforce_rate_limit(*, subject: str, action: str, limit: int, period_seconds: int) -> None:
    """Atomically increment a fixed database window or raise HTTP 429."""
    now = timezone.now()
    window_start = datetime.fromtimestamp(
        int(now.timestamp()) - (int(now.timestamp()) % period_seconds), tz=datetime_timezone.utc
    )
    with transaction.atomic():
        try:
            counter = RateLimitCounter.objects.select_for_update().get(
                subject=subject, action=action, window_start=window_start
            )
        except RateLimitCounter.DoesNotExist:
            try:
                counter = RateLimitCounter.objects.create(subject=subject, action=action, window_start=window_start, count=0)
            except IntegrityError:
                counter = RateLimitCounter.objects.select_for_update().get(
                    subject=subject, action=action, window_start=window_start
                )
        if counter.count >= limit:
            raise Throttled(wait=period_seconds, detail="Request limit exceeded.")
        counter.count += 1
        counter.save(update_fields=["count"])


def audit(*, action: str, outcome: str, merchant=None, api_key=None, request_id: str = "", metadata: dict | None = None) -> None:
    """Record non-secret security context. Never include credentials or request bodies."""
    SecurityAuditLog.objects.create(
        action=action, outcome=outcome, merchant=merchant, api_key=api_key,
        request_id=request_id[:64], metadata=metadata or {},
    )
