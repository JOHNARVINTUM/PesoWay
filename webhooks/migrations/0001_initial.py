import uuid
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import webhooks.validators


class Migration(migrations.Migration):
    initial = True
    dependencies = [("merchants", "0001_initial")]
    operations = [
        migrations.CreateModel(name="WebhookEndpoint", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("url", models.URLField(max_length=2048, validators=[webhooks.validators.validate_webhook_url])), ("encrypted_secret", models.TextField(editable=False)), ("subscribed_events", models.JSONField(default=list)), ("is_active", models.BooleanField(default=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="webhook_endpoints", to="merchants.merchant")),
        ]),
        migrations.CreateModel(name="WebhookEvent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("event_type", models.CharField(max_length=80)), ("payload", models.JSONField()), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="webhook_events", to="merchants.merchant")),
        ]),
        migrations.CreateModel(name="WebhookDelivery", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("status", models.CharField(choices=[("pending", "Pending"), ("succeeded", "Succeeded"), ("failed", "Failed")], default="pending", max_length=16)), ("attempt_count", models.PositiveSmallIntegerField(default=0)), ("next_attempt_at", models.DateTimeField(default=django.utils.timezone.now)), ("delivered_at", models.DateTimeField(blank=True, null=True)), ("last_status_code", models.PositiveSmallIntegerField(blank=True, null=True)), ("last_error", models.CharField(blank=True, max_length=256)),
            ("endpoint", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deliveries", to="webhooks.webhookendpoint")), ("event", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="deliveries", to="webhooks.webhookevent")),
        ]),
        migrations.AddConstraint(model_name="webhookdelivery", constraint=models.UniqueConstraint(fields=("endpoint", "event"), name="webhook_delivery_once")),
        migrations.AddIndex(model_name="webhookendpoint", index=models.Index(fields=["merchant", "is_active"], name="webhooks_we_merchan_d9659e_idx")), migrations.AddIndex(model_name="webhookevent", index=models.Index(fields=["merchant", "created_at"], name="webhooks_we_merchan_2f90c7_idx")), migrations.AddIndex(model_name="webhookevent", index=models.Index(fields=["event_type", "created_at"], name="webhooks_we_event_t_0cf7ec_idx")), migrations.AddIndex(model_name="webhookdelivery", index=models.Index(fields=["status", "next_attempt_at"], name="webhooks_we_status_afd94b_idx")),
    ]
