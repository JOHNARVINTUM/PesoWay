"""Merchant identity and API credential records."""
from hashlib import sha256
import secrets

from django.conf import settings
from django.db import models
from django.utils.crypto import constant_time_compare
from django.utils import timezone


class Merchant(models.Model):
    name = models.CharField(max_length=120)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="merchants")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self) -> str:
        return self.name


class Application(models.Model):
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="applications")
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["merchant", "name"], name="merchant_application_name_unique")]


class APIKey(models.Model):
    """A scoped credential. Raw secrets are returned only by ``create_secret``."""
    prefix = models.CharField(max_length=16, unique=True, editable=False)
    secret_hash = models.CharField(max_length=64, unique=True, editable=False)
    application = models.ForeignKey(Application, on_delete=models.PROTECT, related_name="api_keys")
    scopes = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(blank=True, null=True)

    @classmethod
    def create_secret(cls, *, application: Application, scopes: list[str]) -> tuple["APIKey", str]:
        """Create a key and its one-time raw value; never persist the raw value."""
        prefix = f"pw_{secrets.token_urlsafe(6)}"
        raw_secret = secrets.token_urlsafe(32)
        raw_key = f"{prefix}.{raw_secret}"
        key = cls.objects.create(
            prefix=prefix,
            secret_hash=sha256(raw_key.encode("utf-8")).hexdigest(),
            application=application,
            scopes=sorted(set(scopes)),
        )
        return key, raw_key

    @classmethod
    def authenticate(cls, raw_key: str) -> "APIKey | None":
        """Return an active key after a constant-time hash comparison."""
        if not raw_key or len(raw_key) > 256 or raw_key.count(".") != 1:
            return None
        prefix = raw_key.split(".", 1)[0]
        try:
            key = cls.objects.select_related("application__merchant").get(prefix=prefix, is_active=True)
        except cls.DoesNotExist:
            return None
        supplied_hash = sha256(raw_key.encode("utf-8")).hexdigest()
        if not constant_time_compare(key.secret_hash, supplied_hash):
            return None
        if not key.application.is_active or not key.application.merchant.is_active:
            return None
        return key

    def revoke(self) -> None:
        self.is_active = False
        self.revoked_at = timezone.now()
        self.save(update_fields=["is_active", "revoked_at"])

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes

