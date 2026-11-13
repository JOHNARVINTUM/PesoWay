from django.core.management.base import BaseCommand

from webhooks.services import process_due_deliveries


class Command(BaseCommand):
    help = "Deliver due PesoWay webhook outbox records once. Schedule externally."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)

    def handle(self, *args, **options):
        summary = process_due_deliveries(limit=options["limit"])
        self.stdout.write(self.style.SUCCESS(
            "Processed {processed} webhook delivery records "
            "({succeeded} succeeded, {failed} failed).".format(**summary)
        ))
