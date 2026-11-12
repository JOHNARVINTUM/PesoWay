from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient


class SessionAuthTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operator", password="a-secure-password")
        self.client = APIClient()

    def test_login_rejects_unknown_fields_and_creates_session(self):
        invalid = self.client.post("/api/v1/auth/login/", {"username": "operator", "password": "a-secure-password", "role": "staff"}, format="json")
        self.assertEqual(invalid.status_code, 400)
        response = self.client.post("/api/v1/auth/login/", {"username": "operator", "password": "a-secure-password"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("sessionid", response.cookies)
