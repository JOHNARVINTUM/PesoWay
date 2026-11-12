from datetime import timedelta
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import RateLimitCounter


class CleanupCommandTests(TestCase):
    def test_dry_run_does_not_delete_records(self):
        counter = RateLimitCounter.objects.create(subject="merchant:old", action="old", window_start=timezone.now() - timedelta(days=3), count=1)
        output = StringIO()
        call_command("cleanup_pesoway_data", stdout=output)
        self.assertTrue(RateLimitCounter.objects.filter(pk=counter.pk).exists())
        self.assertIn("Dry run", output.getvalue())
