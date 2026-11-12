from django.apps import AppConfig


class SecurityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "security"

    def ready(self):
        # Register OpenAPI extensions after Django's app registry is initialized.
        from . import openapi  # noqa: F401

