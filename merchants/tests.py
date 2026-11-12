from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import APIKey, Application, Merchant


class APIKeyTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="merchant", password="a-secure-password")
        self.merchant = Merchant.objects.create(name="Acme Store", owner=self.owner)
        self.application = Application.objects.create(merchant=self.merchant, name="Checkout")

    def test_raw_secret_is_not_persisted_and_authenticates(self):
        key, raw_key = APIKey.create_secret(application=self.application, scopes=["payments:read"])

        key.refresh_from_db()
        self.assertNotIn(raw_key, key.secret_hash)
        self.assertEqual(APIKey.authenticate(raw_key), key)
        self.assertTrue(key.has_scope("payments:read"))

    def test_revoked_or_suspended_merchant_key_cannot_authenticate(self):
        key, raw_key = APIKey.create_secret(application=self.application, scopes=[])
        key.is_active = False
        key.save(update_fields=["is_active"])
        self.assertIsNone(APIKey.authenticate(raw_key))

        key.is_active = True
        key.save(update_fields=["is_active"])
        self.merchant.is_active = False
        self.merchant.save(update_fields=["is_active"])
        self.assertIsNone(APIKey.authenticate(raw_key))

