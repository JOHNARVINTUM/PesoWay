from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Application, Merchant


class APIKeyManagementTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="key-owner", password="a-secure-password")
        self.merchant = Merchant.objects.create(name="Key Merchant", owner=self.owner)
        self.app = Application.objects.create(merchant=self.merchant, name="Key App")
        self.client = APIClient()
        self.client.force_login(self.owner)

    def test_owner_creates_once_visible_key_then_revokes(self):
        response = self.client.post("/api/v1/merchant/api-keys/", {"application_id": self.app.pk, "scopes": ["payments:read"]}, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["data"]["secret"].startswith("pw_"))
        revoke = self.client.post(f"/api/v1/merchant/api-keys/{response.data['data']['id']}/revoke/", format="json")
        self.assertEqual(revoke.status_code, 204)
