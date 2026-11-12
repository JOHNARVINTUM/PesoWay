from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("transactions", "0001_initial")]
    operations = [migrations.AlterField(
        model_name="ledgerentry",
        name="entry_type",
        field=models.CharField(choices=[("payment_created", "Payment created"), ("payment_succeeded", "Payment succeeded"), ("payment_canceled", "Payment canceled"), ("refund", "Refund")], max_length=32),
    )]
