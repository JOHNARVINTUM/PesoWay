from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from merchants.models import Merchant


class TestConsoleTests(TestCase):
    @override_settings(DEBUG=True)
    def test_owner_can_open_local_test_console(self):
        owner = get_user_model().objects.create_user(username="console-owner", password="a-secure-password")
        Merchant.objects.create(name="Console Merchant", owner=owner)
        self.client.force_login(owner)
        response = self.client.get("/dashboard/test-console/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment Flight Deck")

    def test_public_product_and_developer_pages_are_available(self):
        home = self.client.get("/")
        docs = self.client.get("/developers/")
        self.assertEqual(home.status_code, 200)
        self.assertContains(home, "Build the flow")
        self.assertEqual(docs.status_code, 200)
        self.assertContains(docs, "PesoWay developer docs")
