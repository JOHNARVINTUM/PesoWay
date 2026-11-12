from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIRequestFactory

from merchants.models import APIKey, Application, Merchant
from .authentication import ScopedAPIKeyAuthentication


class APIKeyAuthenticationTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="owner", password="a-secure-password")
        merchant = Merchant.objects.create(name="Secure Store", owner=owner)
        app = Application.objects.create(merchant=merchant, name="API")
        self.key, self.raw_key = APIKey.create_secret(application=app, scopes=["payments:read"])
        self.factory = APIRequestFactory()

    def test_bearer_key_produces_merchant_principal(self):
        request = self.factory.get("/", HTTP_AUTHORIZATION=f"Bearer {self.raw_key}")
        user, auth = ScopedAPIKeyAuthentication().authenticate(request)
        self.assertEqual(user.merchant, self.key.application.merchant)
        self.assertEqual(auth, self.key)

    def test_malformed_authorization_header_is_rejected(self):
        request = self.factory.get("/", HTTP_AUTHORIZATION="Token not-a-key")
        with self.assertRaisesMessage(Exception, "Invalid authorization header"):
            ScopedAPIKeyAuthentication().authenticate(request)

