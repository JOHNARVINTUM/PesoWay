from django.core.management.base import BaseCommand, CommandError

from merchants.models import APIKey, Application
from merchants.serializers import ALLOWED_SCOPES


class Command(BaseCommand):
    help = "Create a scoped merchant API key and print its raw value exactly once."

    def add_arguments(self, parser):
        parser.add_argument("--application", type=int, required=True, help="Application primary key.")
        parser.add_argument("--scope", action="append", required=True, choices=sorted(ALLOWED_SCOPES), help="Repeat for each permitted scope.")

    def handle(self, *args, **options):
        try:
            application = Application.objects.get(pk=options["application"], is_active=True, merchant__is_active=True)
        except Application.DoesNotExist as error:
            raise CommandError("Active application was not found.") from error
        key, raw_key = APIKey.create_secret(application=application, scopes=options["scope"])
        self.stdout.write(self.style.SUCCESS(f"Created API key {key.prefix}. Store the following value now; it cannot be retrieved again:"))
        self.stdout.write(raw_key)
