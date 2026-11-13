from unittest.mock import MagicMock, patch
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from merchants.models import APIKey, Application, Merchant
from .models import WebhookDelivery, WebhookEndpoint
from .services import create_event, deliver_once, delivery_payload, mark_delivery_result, process_due_deliveries, sign_payload


class WebhookTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="webhook-owner", password="a-secure-password")
        self.merchant = Merchant.objects.create(name="Webhook Merchant", owner=owner)
        application = Application.objects.create(merchant=self.merchant, name="Webhook App")
        _, self.raw_key = APIKey.create_secret(application=application, scopes=["webhooks:write"])

    @patch("webhooks.models.validate_webhook_url")
    def test_outbox_creates_only_matching_endpoint_delivery_and_signs_payload(self, _validate):
        endpoint, secret = WebhookEndpoint.create_secret(merchant=self.merchant, url="https://hooks.example.test/event", subscribed_events=["payment_intent.created"])
        event = create_event(merchant=self.merchant, event_type="payment_intent.created", data={"payment_intent": "abc"})
        delivery = WebhookDelivery.objects.get(endpoint=endpoint, event=event)
        payload = delivery_payload(delivery)
        signature = sign_payload(payload=payload, secret=secret, timestamp=123)
        self.assertEqual(len(signature), 64)
        self.assertNotIn(secret, payload.decode())

    @patch("webhooks.models.validate_webhook_url")
    def test_failures_back_off_then_become_terminal(self, _validate):
        endpoint, _ = WebhookEndpoint.create_secret(merchant=self.merchant, url="https://hooks.example.test/event", subscribed_events=["payment_intent.created"])
        event = create_event(merchant=self.merchant, event_type="payment_intent.created", data={})
        delivery = WebhookDelivery.objects.get(endpoint=endpoint, event=event)
        mark_delivery_result(delivery=delivery, succeeded=False, error="Delivery failed.")
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.Status.PENDING)
        for _ in range(4):
            mark_delivery_result(delivery=delivery, succeeded=False, error="Delivery failed.")
            delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.Status.FAILED)
        self.assertEqual(delivery.attempt_count, 5)

    @patch("webhooks.models.validate_webhook_url")
    @patch("webhooks.serializers.validate_webhook_url")
    def test_endpoint_secret_is_returned_once_and_not_stored_raw(self, _serializer_validate, _model_validate):
        response = APIClient().post("/api/v1/webhook-endpoints/", {"url": "https://hooks.example.test/event", "subscribed_events": ["payment_intent.created"]}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.raw_key}")
        self.assertEqual(response.status_code, 201)
        endpoint = WebhookEndpoint.objects.get(pk=response.data["data"]["id"])
        self.assertNotIn(response.data["data"]["secret"], endpoint.encrypted_secret)

    def test_events_are_merchant_scoped_and_require_read_scope(self):
        create_event(merchant=self.merchant, event_type="payment_intent.created", data={"payment_intent": "abc"})
        _, read_key = APIKey.create_secret(application=Application.objects.get(merchant=self.merchant), scopes=["webhooks:read"])
        response = APIClient().get("/api/v1/webhook-events/", HTTP_AUTHORIZATION=f"Bearer {read_key}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["data"]), 1)

    @patch("webhooks.models.validate_webhook_url")
    @patch("webhooks.services.validate_webhook_url")
    @patch("webhooks.services.build_opener")
    def test_successful_outbound_delivery_is_recorded_once(self, mock_opener, _service_validate, _model_validate):
        endpoint, _ = WebhookEndpoint.create_secret(merchant=self.merchant, url="https://hooks.example.test/event", subscribed_events=["payment_intent.created"])
        event = create_event(merchant=self.merchant, event_type="payment_intent.created", data={})
        delivery = WebhookDelivery.objects.get(endpoint=endpoint, event=event)
        response = MagicMock(status=204)
        mock_opener.return_value.open.return_value.__enter__.return_value = response

        deliver_once(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.Status.SUCCEEDED)
        self.assertEqual(delivery.attempt_count, 1)

        self.assertEqual(process_due_deliveries(), {"processed": 0, "succeeded": 0, "failed": 0})
        self.assertEqual(mock_opener.return_value.open.call_count, 1)

    @patch("webhooks.models.validate_webhook_url")
    @patch("webhooks.services.validate_webhook_url")
    @patch("webhooks.services.build_opener")
    def test_failed_outbound_delivery_preserves_retry_policy(self, mock_opener, _service_validate, _model_validate):
        endpoint, _ = WebhookEndpoint.create_secret(merchant=self.merchant, url="https://hooks.example.test/event", subscribed_events=["payment_intent.created"])
        event = create_event(merchant=self.merchant, event_type="payment_intent.created", data={})
        delivery = WebhookDelivery.objects.get(endpoint=endpoint, event=event)
        mock_opener.return_value.open.side_effect = OSError("network unavailable")

        deliver_once(delivery)
        delivery.refresh_from_db()
        self.assertEqual(delivery.status, WebhookDelivery.Status.PENDING)
        self.assertEqual(delivery.attempt_count, 1)
        self.assertGreater(delivery.next_attempt_at, timezone.now())

    @patch("webhooks.models.validate_webhook_url")
    @patch("webhooks.services.deliver_once")
    def test_processor_claims_only_due_deliveries(self, mock_deliver_once, _model_validate):
        endpoint, _ = WebhookEndpoint.create_secret(merchant=self.merchant, url="https://hooks.example.test/event", subscribed_events=["payment_intent.created"])
        due_event = create_event(merchant=self.merchant, event_type="payment_intent.created", data={"kind": "due"})
        future_event = create_event(merchant=self.merchant, event_type="payment_intent.created", data={"kind": "future"})
        due_delivery = WebhookDelivery.objects.get(endpoint=endpoint, event=due_event)
        future_delivery = WebhookDelivery.objects.get(endpoint=endpoint, event=future_event)
        future_delivery.next_attempt_at = timezone.now() + timedelta(minutes=10)
        future_delivery.save(update_fields=["next_attempt_at"])

        def succeed(delivery):
            mark_delivery_result(delivery=delivery, succeeded=True)

        mock_deliver_once.side_effect = succeed
        self.assertEqual(process_due_deliveries(), {"processed": 1, "succeeded": 1, "failed": 0})
        due_delivery.refresh_from_db()
        future_delivery.refresh_from_db()
        self.assertEqual(due_delivery.status, WebhookDelivery.Status.SUCCEEDED)
        self.assertEqual(future_delivery.status, WebhookDelivery.Status.PENDING)
        mock_deliver_once.assert_called_once()

    @override_settings(CRON_SECRET="cron-test-secret")
    def test_cron_rejects_missing_and_invalid_credentials(self):
        client = APIClient()
        for authorization in (None, "Bearer wrong-secret"):
            response = client.get("/internal/cron/deliver-webhooks/", HTTP_AUTHORIZATION=authorization) if authorization else client.get("/internal/cron/deliver-webhooks/")
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.data["error"]["message"], "Request could not be completed.")

    @override_settings(CRON_SECRET="cron-test-secret")
    @patch("webhooks.views.process_due_deliveries")
    def test_cron_with_valid_credential_invokes_due_delivery_processor(self, process_due):
        process_due.return_value = {"processed": 1, "succeeded": 1, "failed": 0}
        response = APIClient().get("/internal/cron/deliver-webhooks/", HTTP_AUTHORIZATION="Bearer cron-test-secret")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"], process_due.return_value)
        process_due.assert_called_once_with(limit=100)
