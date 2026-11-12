import threading

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TransactionTestCase, skipUnlessDBFeature

from merchants.models import APIKey, Application, Merchant
from .models import PaymentIntent
from .services import create_payment_intent


@skipUnlessDBFeature("has_select_for_update")
class PostgreSQLIdempotencyConcurrencyTests(TransactionTestCase):
    """Run this suite against PostgreSQL; SQLite cannot validate row-lock behavior."""
    def setUp(self):
        if connection.vendor != "postgresql":
            self.skipTest("Concurrency test requires PostgreSQL.")
        owner = get_user_model().objects.create_user(username="pg-owner", password="a-secure-password")
        self.merchant = Merchant.objects.create(name="PG Merchant", owner=owner)
        self.application = Application.objects.create(merchant=self.merchant, name="PG App")
        self.key, _ = APIKey.create_secret(application=self.application, scopes=["payments:write"])

    def test_concurrent_identical_requests_create_one_intent(self):
        barrier = threading.Barrier(2)
        results, errors = [], []
        data = {"amount_centavos": 100, "currency": "PHP", "merchant_reference": "pg-concurrent", "expires_in_minutes": 30}

        def worker():
            try:
                merchant = Merchant.objects.get(pk=self.merchant.pk)
                application = Application.objects.get(pk=self.application.pk)
                key = APIKey.objects.get(pk=self.key.pk)
                barrier.wait()
                results.append(create_payment_intent(merchant=merchant, application=application, api_key=key, data=data, idempotency_key="same-pg-key"))
            except Exception as error:  # assertions occur in the main test thread
                errors.append(error)

        threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(errors, [])
        self.assertEqual(len(results), 2)
        self.assertEqual(PaymentIntent.objects.filter(merchant=self.merchant).count(), 1)
