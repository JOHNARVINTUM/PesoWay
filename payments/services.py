import hashlib
import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import APIException, ValidationError

from security.services import audit
from webhooks.services import create_event
from transactions.services import record_entry
from .models import IdempotencyRecord, PaymentIntent


class Conflict(APIException):
    status_code = 409
    default_code = "idempotency_conflict"
    default_detail = "Idempotency key was already used with a different request."


LEGAL_TRANSITIONS = {
    PaymentIntent.Status.CREATED: {PaymentIntent.Status.REQUIRES_PAYMENT_METHOD, PaymentIntent.Status.CANCELED, PaymentIntent.Status.EXPIRED},
    PaymentIntent.Status.REQUIRES_PAYMENT_METHOD: {PaymentIntent.Status.PROCESSING, PaymentIntent.Status.CANCELED, PaymentIntent.Status.EXPIRED},
    PaymentIntent.Status.PROCESSING: {PaymentIntent.Status.REQUIRES_PAYMENT_METHOD, PaymentIntent.Status.SUCCEEDED, PaymentIntent.Status.FAILED, PaymentIntent.Status.CANCELED, PaymentIntent.Status.EXPIRED},
    PaymentIntent.Status.FAILED: {PaymentIntent.Status.REQUIRES_PAYMENT_METHOD, PaymentIntent.Status.CANCELED, PaymentIntent.Status.EXPIRED},
    PaymentIntent.Status.SUCCEEDED: set(),
    PaymentIntent.Status.CANCELED: set(),
    PaymentIntent.Status.EXPIRED: set(),
}


def transition_intent(intent: PaymentIntent, target: str) -> PaymentIntent:
    if target not in LEGAL_TRANSITIONS[intent.status]:
        raise ValidationError({"status": ["Illegal payment state transition."]})
    intent.status = target
    if target in {PaymentIntent.Status.SUCCEEDED, PaymentIntent.Status.CANCELED, PaymentIntent.Status.EXPIRED}:
        intent.completed_at = timezone.now()
        intent.save(update_fields=["status", "completed_at"])
    else:
        intent.save(update_fields=["status"])
    return intent


def _fingerprint(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def create_payment_intent(*, merchant, application, api_key, data: dict, idempotency_key: str, request_id: str = "") -> tuple[PaymentIntent, dict, int, bool]:
    fingerprint = _fingerprint(data)
    with transaction.atomic():
        try:
            record = IdempotencyRecord.objects.select_for_update().get(merchant=merchant, operation="payment_intent.create", key=idempotency_key)
            if record.request_fingerprint != fingerprint:
                raise Conflict()
            if record.response_body is None:
                raise Conflict("A request with this idempotency key is still processing.")
            return record.payment_intent, record.response_body, record.http_status, True
        except IdempotencyRecord.DoesNotExist:
            try:
                # Savepoint keeps the outer transaction usable if another request wins the unique-key race.
                with transaction.atomic():
                    record = IdempotencyRecord.objects.create(merchant=merchant, operation="payment_intent.create", key=idempotency_key, request_fingerprint=fingerprint)
            except IntegrityError:
                # Another PostgreSQL transaction won; its record becomes visible after this savepoint rolls back.
                record = IdempotencyRecord.objects.select_for_update().get(merchant=merchant, operation="payment_intent.create", key=idempotency_key)
                if record.request_fingerprint != fingerprint:
                    raise Conflict()
                if record.response_body is None:
                    raise Conflict("A request with this idempotency key is still processing.")
                return record.payment_intent, record.response_body, record.http_status, True
        try:
            with transaction.atomic():
                intent = PaymentIntent.objects.create(
                    merchant=merchant, application=application, amount_centavos=data["amount_centavos"], currency=data["currency"],
            merchant_reference=data["merchant_reference"], description=data.get("description", ""), return_url=data.get("return_url", ""),
                    expires_at=timezone.now() + timedelta(minutes=data["expires_in_minutes"]),
                )
        except IntegrityError as error:
            if "merchant_payment_reference_unique" in str(error) or "merchant_reference" in str(error):
                raise ValidationError({"merchant_reference": ["This reference has already been used by this merchant."]})
            raise
        response = {"data": {"id": str(intent.public_id), "amount_centavos": intent.amount_centavos, "currency": intent.currency,
                             "merchant_reference": intent.merchant_reference, "description": intent.description, "return_url": intent.return_url, "status": intent.status,
                             "checkout_url": f"/checkout/{intent.public_id}/", "created_at": intent.created_at.isoformat(), "expires_at": intent.expires_at.isoformat(), "completed_at": None}}
        record.payment_intent = intent
        record.http_status = 201
        record.response_body = response
        record.save(update_fields=["payment_intent", "http_status", "response_body"])
        create_event(merchant=merchant, event_type="payment_intent.created", data={"payment_intent": str(intent.public_id), "status": intent.status})
        record_entry(merchant=merchant, payment_intent=intent, entry_type="payment_created", amount_centavos=intent.amount_centavos, reference=f"pi-create-{intent.public_id}")
        audit(action="payment_intent.create", outcome="success", merchant=merchant, api_key=api_key, request_id=request_id, metadata={"payment_intent": str(intent.public_id)})
        return intent, response, 201, False


def cancel_payment_intent(*, intent: PaymentIntent, api_key, request_id: str = "") -> PaymentIntent:
    with transaction.atomic():
        intent = PaymentIntent.objects.select_for_update().get(pk=intent.pk)
        if intent.is_expired() and intent.status not in {PaymentIntent.Status.SUCCEEDED, PaymentIntent.Status.CANCELED, PaymentIntent.Status.EXPIRED}:
            transition_intent(intent, PaymentIntent.Status.EXPIRED)
        if intent.status not in {PaymentIntent.Status.CREATED, PaymentIntent.Status.REQUIRES_PAYMENT_METHOD, PaymentIntent.Status.PROCESSING, PaymentIntent.Status.FAILED}:
            raise ValidationError({"status": ["Payment intent cannot be canceled in its current state."]})
        transition_intent(intent, PaymentIntent.Status.CANCELED)
        create_event(merchant=intent.merchant, event_type="payment_intent.canceled", data={"payment_intent": str(intent.public_id), "status": intent.status})
        record_entry(merchant=intent.merchant, payment_intent=intent, entry_type="payment_canceled", amount_centavos=0, reference=f"pi-cancel-{intent.public_id}")
        audit(action="payment_intent.cancel", outcome="success", merchant=intent.merchant, api_key=api_key, request_id=request_id, metadata={"payment_intent": str(intent.public_id)})
        return intent
