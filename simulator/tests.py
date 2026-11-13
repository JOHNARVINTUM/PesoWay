from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from unittest.mock import patch

from merchants.models import APIKey, Application, Merchant
from payments.models import PaymentIntent


class SimulatorFlowTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="sim-owner", password="a-secure-password")
        merchant = Merchant.objects.create(name="Simulator Merchant", owner=owner)
        app = Application.objects.create(merchant=merchant, name="Simulator App")
        _, self.key = APIKey.create_secret(application=app, scopes=["payments:write", "simulator:write"])
        self.client = APIClient()
        response = self.client.post("/api/v1/payment-intents/", {"amount_centavos": 1000, "currency": "PHP", "merchant_reference": "sim-order"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}", HTTP_IDEMPOTENCY_KEY="sim-order-key")
        self.intent_id = response.data["data"]["id"]

    @patch("simulator.services.process_due_deliveries")
    def test_successful_simulation_completes_intent_and_requests_immediate_webhook_delivery(self, process_due):
        attempt = self.client.post(f"/api/v1/payment-intents/{self.intent_id}/attempts/", {"method": "gcash"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(attempt.status_code, 201)
        with self.captureOnCommitCallbacks(execute=True):
            completed = self.client.post(f"/api/v1/simulator/payment-attempts/{attempt.data['data']['attempt_id']}/complete/", {"scenario": "succeeded"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["data"]["payment_intent_status"], "succeeded")
        self.assertEqual(process_due.call_count, 1)
        self.assertEqual(process_due.call_args.kwargs["limit"], 1)
        self.assertEqual(process_due.call_args.kwargs["event"].event_type, "payment_intent.succeeded")

    def test_failed_simulation_leaves_intent_retryable(self):
        attempt = self.client.post(f"/api/v1/payment-intents/{self.intent_id}/attempts/", {"method": "card"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        completed = self.client.post(f"/api/v1/simulator/payment-attempts/{attempt.data['data']['attempt_id']}/complete/", {"scenario": "failed"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["data"]["payment_intent_status"], "requires_payment_method")

    @override_settings(DEBUG=True, PESOWAY_SIMULATOR_ENABLED=True)
    def test_local_hosted_checkout_requires_test_authorization_before_completion(self):
        intent = PaymentIntent.objects.get(public_id=self.intent_id)
        page = self.client.get(f"/checkout/{intent.public_id}/")
        self.assertEqual(page.status_code, 200)
        selected = self.client.post(f"/checkout/{intent.public_id}/", {"method": "maya"})
        self.assertEqual(selected.status_code, 302)
        intent.refresh_from_db()
        self.assertNotEqual(intent.status, PaymentIntent.Status.SUCCEEDED)
        authorization = self.client.get(selected["Location"])
        self.assertContains(authorization, "Authorize test payment")
        paid = self.client.post(selected["Location"], {"decision": "authorize"})
        self.assertEqual(paid.status_code, 200)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.SUCCEEDED)
        self.assertContains(paid, "Simulated payment successful")

    @override_settings(DEBUG=True, PESOWAY_SIMULATOR_ENABLED=True)
    def test_hosted_checkout_redirects_to_validated_local_return_url(self):
        intent = PaymentIntent.objects.get(public_id=self.intent_id)
        intent.return_url = "http://localhost:3000/checkout/complete?source=pesoway"
        intent.save(update_fields=["return_url"])
        selected = self.client.post(f"/checkout/{intent.public_id}/", {"method": "gcash"})
        response = self.client.post(selected["Location"], {"decision": "authorize"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"payment_intent={intent.public_id}", response["Location"])
        self.assertIn("status=succeeded", response["Location"])

    @override_settings(DEBUG=False, PESOWAY_SIMULATOR_ENABLED=False)
    def test_hosted_checkout_is_disabled_without_explicit_simulator_flag(self):
        response = self.client.get(f"/checkout/{self.intent_id}/")
        self.assertEqual(response.status_code, 404)

    @override_settings(DEBUG=False, PESOWAY_SIMULATOR_ENABLED=True)
    def test_hosted_checkout_can_run_with_production_debug_disabled(self):
        response = self.client.get(f"/checkout/{self.intent_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SIMULATION")
