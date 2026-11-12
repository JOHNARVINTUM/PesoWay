from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.test import TestCase
from rest_framework.test import APIClient

from merchants.models import APIKey, Application, Merchant
from payments.models import PaymentIntent
from .models import LedgerEntry


class RefundAndLedgerTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="ledger-owner", password="a-secure-password")
        self.merchant = Merchant.objects.create(name="Ledger Merchant", owner=owner)
        app = Application.objects.create(merchant=self.merchant, name="Ledger App")
        _, self.key = APIKey.create_secret(application=app, scopes=["refunds:write", "transactions:read"])
        self.intent = PaymentIntent.objects.create(merchant=self.merchant, application=app, amount_centavos=1000, currency="PHP", merchant_reference="paid-order", status=PaymentIntent.Status.SUCCEEDED, expires_at="2030-01-01T00:00:00Z")

    def test_refund_creates_negative_immutable_ledger_entry(self):
        response = APIClient().post("/api/v1/refunds/", {"payment_intent_id": str(self.intent.public_id), "amount_centavos": 400, "merchant_reference": "refund-1"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(response.status_code, 201)
        entry = LedgerEntry.objects.get(entry_type=LedgerEntry.EntryType.REFUND)
        self.assertEqual(entry.amount_centavos, -400)
        entry.reference = "tampered"
        with self.assertRaises(DjangoValidationError):
            entry.save()

    def test_refund_cannot_exceed_successful_payment(self):
        client = APIClient()
        first = client.post("/api/v1/refunds/", {"payment_intent_id": str(self.intent.public_id), "amount_centavos": 800, "merchant_reference": "refund-a"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        second = client.post("/api/v1/refunds/", {"payment_intent_id": str(self.intent.public_id), "amount_centavos": 300, "merchant_reference": "refund-b"}, format="json", HTTP_AUTHORIZATION=f"Bearer {self.key}")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 400)
