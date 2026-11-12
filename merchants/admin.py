from django.contrib import admin
from .models import APIKey, Application, Merchant

admin.site.register((Merchant, Application, APIKey))

