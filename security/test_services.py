from django.test import TestCase
from rest_framework.exceptions import Throttled

from .models import RateLimitCounter
from .services import enforce_rate_limit


class RateLimitTests(TestCase):
    def test_atomic_database_counter_enforces_limit(self):
        enforce_rate_limit(subject="merchant:1", action="test", limit=1, period_seconds=60)
        with self.assertRaises(Throttled):
            enforce_rate_limit(subject="merchant:1", action="test", limit=1, period_seconds=60)
        self.assertEqual(RateLimitCounter.objects.get(subject="merchant:1", action="test").count, 1)
