import hashlib
import hmac
import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .crypto import decrypt_secret
from .models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from .validators import validate_webhook_url


MAX_ATTEMPTS = 5
DELIVERY_TIMEOUT_SECONDS = 5


def create_event(*, merchant, event_type: str, data: dict) -> WebhookEvent:
    """Transactional outbox entry and its endpoint deliveries; no network happens here."""
    event = WebhookEvent.objects.create(merchant=merchant, event_type=event_type, payload=data)
    for endpoint in WebhookEndpoint.objects.filter(merchant=merchant, is_active=True):
        if event_type in endpoint.subscribed_events:
            WebhookDelivery.objects.create(endpoint=endpoint, event=event)
    return event


def delivery_payload(delivery: WebhookDelivery) -> bytes:
    value = {"id": str(delivery.event.public_id), "type": delivery.event.event_type, "created_at": delivery.event.created_at.isoformat(), "data": delivery.event.payload}
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_payload(*, payload: bytes, secret: str, timestamp: int) -> str:
    signed = f"{timestamp}.".encode("ascii") + payload
    return hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()


def mark_delivery_result(*, delivery: WebhookDelivery, succeeded: bool, status_code: int | None = None, error: str = "") -> None:
    delivery.attempt_count += 1
    delivery.last_status_code = status_code
    delivery.last_error = error[:256]
    if succeeded:
        delivery.status = WebhookDelivery.Status.SUCCEEDED
        delivery.delivered_at = timezone.now()
        delivery.save(update_fields=["attempt_count", "last_status_code", "last_error", "status", "delivered_at"])
        return
    if delivery.attempt_count >= MAX_ATTEMPTS:
        delivery.status = WebhookDelivery.Status.FAILED
    else:
        delivery.next_attempt_at = timezone.now() + timedelta(seconds=min(3600, 60 * (2 ** (delivery.attempt_count - 1))))
    delivery.save(update_fields=["attempt_count", "last_status_code", "last_error", "status", "next_attempt_at"])


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def claim_due_deliveries(*, limit: int = 100) -> list[WebhookDelivery]:
    """Claim work by moving its schedule forward before making any network call."""
    now = timezone.now()
    with transaction.atomic():
        queryset = WebhookDelivery.objects.select_related("endpoint", "event").filter(
            status=WebhookDelivery.Status.PENDING, next_attempt_at__lte=now
        ).order_by("id")
        if transaction.get_connection().features.has_select_for_update_skip_locked:
            queryset = queryset.select_for_update(skip_locked=True)
        else:
            queryset = queryset.select_for_update()
        deliveries = list(queryset[:limit])
        for delivery in deliveries:
            delivery.next_attempt_at = now + timedelta(minutes=5)
            delivery.save(update_fields=["next_attempt_at"])
    return deliveries


def deliver_once(delivery: WebhookDelivery) -> None:
    """Send one signed event. URL validation is repeated to mitigate DNS rebinding."""
    validate_webhook_url(delivery.endpoint.url)
    payload = delivery_payload(delivery)
    timestamp = int(timezone.now().timestamp())
    signature = sign_payload(payload=payload, secret=decrypt_secret(delivery.endpoint.encrypted_secret), timestamp=timestamp)
    request = Request(delivery.endpoint.url, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "User-Agent": "PesoWay-Webhook/1.0",
        "X-PesoWay-Event": str(delivery.event.public_id),
        "X-PesoWay-Timestamp": str(timestamp),
        "X-PesoWay-Signature": f"v1={signature}",
    })
    try:
        with build_opener(_NoRedirect()).open(request, timeout=DELIVERY_TIMEOUT_SECONDS) as response:
            status_code = response.status
        mark_delivery_result(delivery=delivery, succeeded=200 <= status_code < 300, status_code=status_code, error="" if 200 <= status_code < 300 else "Non-success response.")
    except HTTPError as error:
        mark_delivery_result(delivery=delivery, succeeded=False, status_code=error.code, error="Non-success response.")
    except (URLError, OSError, ValueError):
        mark_delivery_result(delivery=delivery, succeeded=False, error="Delivery failed.")
