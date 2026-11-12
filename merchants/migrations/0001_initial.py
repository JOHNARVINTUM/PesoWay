from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name="Merchant", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=120)), ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("owner", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="merchants", to=settings.AUTH_USER_MODEL)),
        ], options={"ordering": ["id"]}),
        migrations.CreateModel(name="Application", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name", models.CharField(max_length=120)), ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="applications", to="merchants.merchant")),
        ]),
        migrations.CreateModel(name="APIKey", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("prefix", models.CharField(editable=False, max_length=16, unique=True)),
            ("secret_hash", models.CharField(editable=False, max_length=64, unique=True)),
            ("scopes", models.JSONField(default=list)), ("is_active", models.BooleanField(default=True)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("revoked_at", models.DateTimeField(blank=True, null=True)),
            ("application", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="api_keys", to="merchants.application")),
        ]),
        migrations.AddConstraint(model_name="application", constraint=models.UniqueConstraint(fields=("merchant", "name"), name="merchant_application_name_unique")),
    ]
