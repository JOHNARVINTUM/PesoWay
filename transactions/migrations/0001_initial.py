import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("merchants", "0001_initial"), ("payments", "0001_initial")]
    operations = [
        migrations.CreateModel(name="LedgerEntry", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("entry_type", models.CharField(choices=[("payment_created", "Payment created"), ("payment_canceled", "Payment canceled"), ("refund", "Refund")], max_length=32)), ("amount_centavos", models.BigIntegerField()), ("currency", models.CharField(default="PHP", max_length=3)), ("reference", models.CharField(max_length=100, unique=True)), ("metadata", models.JSONField(blank=True, default=dict)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="merchants.merchant")), ("payment_intent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="payments.paymentintent")),
        ]),
        migrations.CreateModel(name="Refund", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")), ("public_id", models.UUIDField(default=uuid.uuid4, editable=False, unique=True)), ("amount_centavos", models.PositiveBigIntegerField()), ("currency", models.CharField(default="PHP", max_length=3)), ("merchant_reference", models.CharField(max_length=100)), ("status", models.CharField(choices=[("succeeded", "Simulated succeeded")], default="succeeded", max_length=16)), ("created_at", models.DateTimeField(auto_now_add=True)),
            ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refunds", to="merchants.merchant")), ("payment_intent", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="refunds", to="payments.paymentintent")),
        ]),
        migrations.AddConstraint(model_name="ledgerentry", constraint=models.CheckConstraint(condition=models.Q(("currency", "PHP")), name="ledger_php_only")), migrations.AddConstraint(model_name="refund", constraint=models.CheckConstraint(condition=models.Q(("amount_centavos__gt", 0)), name="refund_amount_positive")), migrations.AddConstraint(model_name="refund", constraint=models.UniqueConstraint(fields=("merchant", "merchant_reference"), name="merchant_refund_reference_unique")),
        migrations.AddIndex(model_name="ledgerentry", index=models.Index(fields=["merchant", "created_at"], name="transaction_merchan_b1bbde_idx")), migrations.AddIndex(model_name="ledgerentry", index=models.Index(fields=["payment_intent", "created_at"], name="transaction_payment_bbf621_idx")), migrations.AddIndex(model_name="refund", index=models.Index(fields=["merchant", "created_at"], name="transaction_merchan_9437ca_idx")), migrations.AddIndex(model_name="refund", index=models.Index(fields=["payment_intent", "created_at"], name="transaction_payment_67df19_idx")),
    ]
