from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("payments", "0001_initial")]
    operations = [migrations.AddField(model_name="paymentintent", name="return_url", field=models.URLField(blank=True, max_length=2048))]
