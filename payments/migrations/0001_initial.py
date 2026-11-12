import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("merchants", "0001_initial")]
    operations = [
        migrations.CreateModel(name="PaymentIntent", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
            ("amount_centavos", models.PositiveBigIntegerField()), ("currency", models.CharField(default="PHP", max_length=3)), ("merchant_reference", models.CharField(max_length=100)), ("description", models.CharField(blank=True, max_length=500)),
            ("status", models.CharField(choices=[("created", "Created"), ("requires_payment_method", "Requires payment method"), ("processing", "Processing"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("canceled", "Canceled"), ("expired", "Expired")], default="created", max_length=32)),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("expires_at", models.DateTimeField()), ("completed_at", models.DateTimeField(blank=True, null=True)),
            ("application", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_intents", to="merchants.application")), ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payment_intents", to="merchants.merchant")),
        ]),
        migrations.CreateModel(name="PaymentAttempt", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("method", models.CharField(choices=[("gcash", "Simulated GCash"), ("maya", "Simulated Maya"), ("card", "Simulated Card"), ("qrph", "Simulated QR Ph")], max_length=16)),
            ("status", models.CharField(choices=[("created", "Created"), ("processing", "Processing"), ("succeeded", "Succeeded"), ("failed", "Failed"), ("canceled", "Canceled")], default="created", max_length=16)), ("reference", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("created_at", models.DateTimeField(auto_now_add=True)), ("completed_at", models.DateTimeField(blank=True, null=True)),
            ("intent", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="attempts", to="payments.paymentintent")),
        ]),
        migrations.CreateModel(name="IdempotencyRecord", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("operation", models.CharField(max_length=64)), ("key", models.CharField(max_length=255)), ("request_fingerprint", models.CharField(max_length=64)), ("http_status", models.PositiveSmallIntegerField(blank=True, null=True)), ("response_body", models.JSONField(blank=True, null=True)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="idempotency_records", to="merchants.merchant")), ("payment_intent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="idempotency_records", to="payments.paymentintent")),
        ]),
        migrations.AddConstraint(model_name="paymentintent", constraint=models.CheckConstraint(condition=models.Q(("amount_centavos__gt", 0)), name="payment_intent_amount_positive")),
        migrations.AddConstraint(model_name="paymentintent", constraint=models.CheckConstraint(condition=models.Q(("currency", "PHP")), name="payment_intent_php_only")),
        migrations.AddConstraint(model_name="paymentintent", constraint=models.UniqueConstraint(fields=("merchant", "merchant_reference"), name="merchant_payment_reference_unique")),
        migrations.AddConstraint(model_name="idempotencyrecord", constraint=models.UniqueConstraint(fields=("merchant", "operation", "key"), name="merchant_idempotency_key_unique")),
        migrations.AddIndex(model_name="paymentintent", index=models.Index(fields=["merchant", "public_id"], name="payments_pa_merchan_8dc8ec_idx")), migrations.AddIndex(model_name="paymentintent", index=models.Index(fields=["merchant", "created_at"], name="payments_pa_merchan_028440_idx")), migrations.AddIndex(model_name="paymentintent", index=models.Index(fields=["status", "expires_at"], name="payments_pa_status_8d1016_idx")), migrations.AddIndex(model_name="idempotencyrecord", index=models.Index(fields=["merchant", "operation", "created_at"], name="payments_id_merchan_885a9f_idx")),
    ]
