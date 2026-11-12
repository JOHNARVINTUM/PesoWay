from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

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

    def test_successful_simulation_completes_intent_server_side(self):
        attempt = self.client.post(f"/api/v1/payment-intents/{self.intent_id}/attempts/", {"method": "gcash"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(attempt.status_code, 201)
        completed = self.client.post(f"/api/v1/simulator/payment-attempts/{attempt.data['data']['attempt_id']}/complete/", {"scenario": "succeeded"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["data"]["payment_intent_status"], "succeeded")

    def test_failed_simulation_leaves_intent_retryable(self):
        attempt = self.client.post(f"/api/v1/payment-intents/{self.intent_id}/attempts/", {"method": "card"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        completed = self.client.post(f"/api/v1/simulator/payment-attempts/{attempt.data['data']['attempt_id']}/complete/", {"scenario": "failed"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(completed.status_code, 200)
        self.assertEqual(completed.data["data"]["payment_intent_status"], "requires_payment_method")

    @override_settings(DEBUG=True)
    def test_local_hosted_checkout_completes_a_simulation(self):
        intent = PaymentIntent.objects.get(public_id=self.intent_id)
        page = self.client.get(f"/checkout/{intent.public_id}/")
        self.assertEqual(page.status_code, 200)
        paid = self.client.post(f"/checkout/{intent.public_id}/", {"method": "maya"})
        self.assertEqual(paid.status_code, 200)
        intent.refresh_from_db()
        self.assertEqual(intent.status, PaymentIntent.Status.SUCCEEDED)
        self.assertContains(paid, "Simulated payment successful")

    @override_settings(DEBUG=True)
    def test_hosted_checkout_redirects_to_validated_local_return_url(self):
        intent = PaymentIntent.objects.get(public_id=self.intent_id)
        intent.return_url = "http://localhost:3000/checkout/complete?source=pesoway"
        intent.save(update_fields=["return_url"])
        response = self.client.post(f"/checkout/{intent.public_id}/", {"method": "gcash"})
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"payment_intent={intent.public_id}", response["Location"])
        self.assertIn("status=succeeded", response["Location"])
