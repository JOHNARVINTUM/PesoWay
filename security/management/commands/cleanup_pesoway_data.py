from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from payments.models import IdempotencyRecord
from security.models import RateLimitCounter, SecurityAuditLog
from webhooks.models import WebhookDelivery, WebhookEvent


class Command(BaseCommand):
    help = "Prune operational records according to retention rules; dry-run unless --execute is passed."

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Perform deletions after reporting counts.")

    def handle(self, *args, **options):
        now = timezone.now()
        candidates = {
            "rate_limit_counters": RateLimitCounter.objects.filter(window_start__lt=now - timedelta(days=2)),
            "idempotency_records": IdempotencyRecord.objects.filter(created_at__lt=now - timedelta(days=7)),
            "security_audit_logs": SecurityAuditLog.objects.filter(created_at__lt=now - timedelta(days=365)),
            "completed_deliveries": WebhookDelivery.objects.filter(
                Q(status=WebhookDelivery.Status.SUCCEEDED, delivered_at__lt=now - timedelta(days=30)) |
                Q(status=WebhookDelivery.Status.FAILED, next_attempt_at__lt=now - timedelta(days=90))
            ),
        }
        counts = {name: queryset.count() for name, queryset in candidates.items()}
        for name, count in counts.items():
            self.stdout.write(f"{name}: {count}")
        if not options["execute"]:
            self.stdout.write(self.style.WARNING("Dry run only. Re-run with --execute to delete these records."))
            return
        with transaction.atomic():
            for queryset in candidates.values():
                queryset.delete()
            orphan_events = WebhookEvent.objects.filter(created_at__lt=now - timedelta(days=90), deliveries__isnull=True)
            orphan_count = orphan_events.count()
            orphan_events.delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted retained operational records and {orphan_count} orphan webhook events."))
