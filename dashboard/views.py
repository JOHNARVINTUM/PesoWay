from django.contrib.auth.decorators import login_required
from django.conf import settings
from decimal import Decimal
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import render

from transactions.models import LedgerEntry


@login_required
def merchant_dashboard(request):
    merchant = request.user.merchants.filter(is_active=True).first()
    if merchant is None:
        return render(request, "dashboard/empty.html", status=403)
    entries = LedgerEntry.objects.filter(merchant=merchant).order_by("-created_at")[:12]
    total = LedgerEntry.objects.filter(merchant=merchant).aggregate(total=Sum("amount_centavos"))["total"] or 0
    return render(request, "dashboard/index.html", {"merchant": merchant, "entries": entries, "total_pesos": Decimal(total) / Decimal(100)})


@login_required
def test_console(request):
    """Local-only browser harness; production API use belongs in trusted server code."""
    if not settings.DEBUG:
        raise Http404
    if not request.user.merchants.filter(is_active=True).exists():
        return render(request, "dashboard/empty.html", status=403)
    return render(request, "dashboard/test_console.html")
