from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from payments.models import PaymentAttempt, PaymentIntent
from payments.services import transition_intent
from security.services import audit
from transactions.services import record_entry
from webhooks.services import create_event, process_due_deliveries


def _deliver_new_event_after_commit(*, merchant, event) -> None:
    """Best-effort immediate delivery; the durable scheduler remains fallback."""
    try:
        # Bound checkout latency. Remaining endpoints and failures stay in the
        # outbox and are picked up by the protected scheduled worker.
        process_due_deliveries(limit=1, merchant=merchant, event=event)
    except Exception:
        # The committed financial state must not be reported as failed merely
        # because an external receiver is temporarily unavailable.
        return


def create_simulated_attempt(*, intent: PaymentIntent, method: str, api_key, request_id: str = "") -> PaymentAttempt:
    with transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(pk=intent.pk)
        if intent.is_expired():
            transition_intent(intent, PaymentIntent.Status.EXPIRED)
            raise ValidationError({"status": ["Payment intent has expired."]})
        if intent.status == PaymentIntent.Status.CREATED:
            transition_intent(intent, PaymentIntent.Status.REQUIRES_PAYMENT_METHOD)
        if intent.status not in {PaymentIntent.Status.REQUIRES_PAYMENT_METHOD, PaymentIntent.Status.FAILED}:
            raise ValidationError({"status": ["Payment intent cannot accept another payment attempt."]})
        attempt = PaymentAttempt.objects.create(intent=intent, method=method)
        audit(action="simulator.attempt.create", outcome="success", merchant=intent.merchant, api_key=api_key, request_id=request_id, metadata={"attempt": str(attempt.reference)})
        return attempt


def complete_simulated_attempt(*, attempt: PaymentAttempt, scenario: str, api_key, request_id: str = "") -> PaymentAttempt:
    """Controlled test-only outcome; callers cannot provide arbitrary payment states."""
    with transaction.atomic():
        attempt = PaymentAttempt.objects.select_for_update().select_related("intent__merchant").get(pk=attempt.pk)
        intent = PaymentIntent.objects.select_for_update().get(pk=attempt.intent_id)
        if attempt.status != PaymentAttempt.Status.CREATED:
            raise ValidationError({"attempt": ["This simulated attempt has already completed."]})
        if intent.is_expired():
            transition_intent(intent, PaymentIntent.Status.EXPIRED)
            attempt.status = PaymentAttempt.Status.CANCELED
        else:
            transition_intent(intent, PaymentIntent.Status.PROCESSING)
            attempt.status = scenario
            if scenario == PaymentAttempt.Status.SUCCEEDED:
                transition_intent(intent, PaymentIntent.Status.SUCCEEDED)
                event = create_event(merchant=intent.merchant, event_type="payment_intent.succeeded", data={"payment_intent": str(intent.public_id), "status": intent.status})
                transaction.on_commit(
                    lambda merchant=intent.merchant, event=event: _deliver_new_event_after_commit(merchant=merchant, event=event)
                )
                record_entry(merchant=intent.merchant, payment_intent=intent, entry_type="payment_succeeded", amount_centavos=intent.amount_centavos, reference=f"pi-success-{intent.public_id}")
            else:
                transition_intent(intent, PaymentIntent.Status.REQUIRES_PAYMENT_METHOD)
        attempt.completed_at = timezone.now()
        attempt.save(update_fields=["status", "completed_at"])
        attempt.intent.refresh_from_db()
        audit(action="simulator.attempt.complete", outcome=scenario, merchant=intent.merchant, api_key=api_key, request_id=request_id, metadata={"attempt": str(attempt.reference)})
        return attempt
