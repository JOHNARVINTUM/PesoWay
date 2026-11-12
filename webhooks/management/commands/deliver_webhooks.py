from django.core.management.base import BaseCommand

from webhooks.services import claim_due_deliveries, deliver_once


class Command(BaseCommand):
    help = "Deliver due PesoWay webhook outbox records once. Schedule externally."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        deliveries = claim_due_deliveries(limit=max(1, min(options["limit"], 1000)))
        for delivery in deliveries:
            deliver_once(delivery)
        self.stdout.write(self.style.SUCCESS(f"Processed {len(deliveries)} webhook delivery records."))
