from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.contrib import messages
from decimal import Decimal
from django.db.models import Sum
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from security.services import audit, enforce_rate_limit
from transactions.models import LedgerEntry
from webhooks.services import process_due_deliveries


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


@login_required
@require_POST
def deliver_due_webhooks(request):
    """Let a merchant owner exercise only their own due webhook test work."""
    merchant = request.user.merchants.filter(is_active=True).first()
    if merchant is None:
        return render(request, "dashboard/empty.html", status=403)
    enforce_rate_limit(
        subject=f"user:{request.user.pk}", action="webhook.delivery.manual", limit=30, period_seconds=3600
    )
    summary = process_due_deliveries(limit=25, merchant=merchant)
    audit(
        action="webhook_delivery.manual_trigger", outcome="success", merchant=merchant,
        metadata=summary,
    )
    messages.success(
        request,
        "Webhook test run complete: {processed} processed, {succeeded} succeeded, {failed} failed.".format(**summary),
    )
    return redirect("merchant-dashboard")
