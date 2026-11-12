from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from merchants.models import APIKey, Application, Merchant
from .models import PaymentIntent
from .services import transition_intent


class PaymentIntentAPITests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="owner", password="a-secure-password")
        self.merchant = Merchant.objects.create(name="Merchant One", owner=owner)
        self.application = Application.objects.create(merchant=self.merchant, name="Checkout")
        self.key, self.raw_key = APIKey.create_secret(application=self.application, scopes=["payments:read", "payments:write"])
        second_owner = get_user_model().objects.create_user(username="other", password="a-secure-password")
        self.other_merchant = Merchant.objects.create(name="Merchant Two", owner=second_owner)
        other_app = Application.objects.create(merchant=self.other_merchant, name="Other Checkout")
        _, self.other_raw_key = APIKey.create_secret(application=other_app, scopes=["payments:read", "payments:write"])
        self.client = APIClient()

    @property
    def payload(self):
        return {"amount_centavos": 12500, "currency": "PHP", "merchant_reference": "order-1001", "description": "Test order"}

    def post(self, payload=None, *, key=None, idem="create-1"):
        return self.client.post("/api/v1/payment-intents/", payload or self.payload, format="json", HTTP_AUTHORIZATION=f"Bearer {key or self.raw_key}", HTTP_IDEMPOTENCY_KEY=idem)

    def test_create_and_retrieve_payment_intent(self):
        response = self.post()
        self.assertEqual(response.status_code, 201)
        public_id = response.data["data"]["id"]
        response = self.client.get(f"/api/v1/payment-intents/{public_id}/", HTTP_AUTHORIZATION=f"Bearer {self.raw_key}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["data"]["amount_centavos"], 12500)

    def test_rejects_bad_input_without_internal_details(self):
        for payload in (
            {**self.payload, "amount_centavos": 0},
            {**self.payload, "currency": "USD"},
            {**self.payload, "merchant_reference": "invalid space"},
            {**self.payload, "untrusted_status": "succeeded"},
        ):
            response = self.post(payload, idem=f"bad-{len(str(payload))}")
            self.assertEqual(response.status_code, 400)
            self.assertIn("error", response.data)
            self.assertNotIn("Traceback", str(response.data))

    def test_missing_or_insufficient_key_is_rejected(self):
        response = self.client.post("/api/v1/payment-intents/", self.payload, format="json", HTTP_IDEMPOTENCY_KEY="none")
        self.assertEqual(response.status_code, 401)
        limited_key, limited_raw = APIKey.create_secret(application=self.application, scopes=["payments:read"])
        response = self.post(key=limited_raw, idem="limited")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "permission_denied")
        self.assertEqual(limited_key.scopes, ["payments:read"])

    def test_cross_merchant_payment_is_not_disclosed(self):
        intent_id = self.post().data["data"]["id"]
        response = self.client.get(f"/api/v1/payment-intents/{intent_id}/", HTTP_AUTHORIZATION=f"Bearer {self.other_raw_key}")
        self.assertEqual(response.status_code, 404)

    def test_idempotency_replays_identical_request_and_rejects_conflict(self):
        first = self.post(idem="same-key")
        replay = self.post(idem="same-key")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(first.data, replay.data)
        conflict = self.post({**self.payload, "amount_centavos": 12600}, idem="same-key")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(PaymentIntent.objects.count(), 1)

    def test_duplicate_reference_rolls_back_the_new_request(self):
        self.assertEqual(self.post(idem="one").status_code, 201)
        response = self.post(idem="two")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(PaymentIntent.objects.count(), 1)

    def test_cancel_and_illegal_terminal_transition(self):
        intent_id = self.post().data["data"]["id"]
        response = self.client.post(f"/api/v1/payment-intents/{intent_id}/cancel/", format="json", HTTP_AUTHORIZATION=f"Bearer {self.raw_key}")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f"/api/v1/payment-intents/{intent_id}/cancel/", format="json", HTTP_AUTHORIZATION=f"Bearer {self.raw_key}")
        self.assertEqual(response.status_code, 400)
        intent = PaymentIntent.objects.get(public_id=intent_id)
        with self.assertRaises(Exception):
            transition_intent(intent, PaymentIntent.Status.SUCCEEDED)
