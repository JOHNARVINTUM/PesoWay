from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from merchants.models import APIKey, Application, Merchant
from .models import WebhookDelivery, WebhookEndpoint
from .services import create_event, delivery_payload, mark_delivery_result, sign_payload


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
