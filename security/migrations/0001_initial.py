from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [("merchants", "0001_initial")]
    operations = [
        migrations.CreateModel(name="RateLimitCounter", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("subject", models.CharField(max_length=80)), ("action", models.CharField(max_length=80)),
            ("window_start", models.DateTimeField()), ("count", models.PositiveIntegerField(default=0)),
        ]),
        migrations.CreateModel(name="SecurityAuditLog", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField(auto_now_add=True)), ("action", models.CharField(max_length=80)),
            ("outcome", models.CharField(max_length=24)), ("request_id", models.CharField(blank=True, max_length=64)),
            ("metadata", models.JSONField(blank=True, default=dict)),
            ("api_key", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="security_audit_logs", to="merchants.apikey")),
            ("merchant", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="security_audit_logs", to="merchants.merchant")),
        ]),
        migrations.AddConstraint(model_name="ratelimitcounter", constraint=models.UniqueConstraint(fields=("subject", "action", "window_start"), name="rate_limit_window_unique")),
        migrations.AddConstraint(model_name="ratelimitcounter", constraint=models.CheckConstraint(condition=models.Q(("count__gte", 0)), name="rate_limit_count_nonnegative")),
        migrations.AddIndex(model_name="ratelimitcounter", index=models.Index(fields=["subject", "action", "window_start"], name="security_ra_subject_9e95dc_idx")),
        migrations.AddIndex(model_name="securityauditlog", index=models.Index(fields=["merchant", "created_at"], name="security_se_merchan_fce992_idx")),
        migrations.AddIndex(model_name="securityauditlog", index=models.Index(fields=["action", "created_at"], name="security_se_action_cf0442_idx")),
    ]
