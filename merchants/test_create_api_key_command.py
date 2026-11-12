from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from .models import Application, Merchant


class CreateAPIKeyCommandTests(TestCase):
    def test_command_creates_scoped_key(self):
        owner = get_user_model().objects.create_user(username="command-owner", password="a-secure-password")
        merchant = Merchant.objects.create(name="Command Merchant", owner=owner)
        application = Application.objects.create(merchant=merchant, name="Command App")
        output = StringIO()
        call_command("create_merchant_api_key", application=application.pk, scope=["payments:read"], stdout=output)
        self.assertIn("pw_", output.getvalue())
