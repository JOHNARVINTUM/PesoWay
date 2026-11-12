from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        MERCHANT = "merchant", "Merchant"
        STAFF = "staff", "Staff"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.MERCHANT)

