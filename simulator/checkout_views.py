from decimal import Decimal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from rest_framework.exceptions import ValidationError

from payments.models import PaymentAttempt, PaymentIntent
from .services import complete_simulated_attempt, create_simulated_attempt


def safe_return_url(url: str, intent: PaymentIntent) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url)
    local = settings.DEBUG and parsed.scheme == "http" and parsed.hostname in {"localhost", "127.0.0.1"}
    if (parsed.scheme != "https" and not local) or not parsed.hostname or parsed.username or parsed.password:
        return None
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.update({"payment_intent": str(intent.public_id), "status": intent.status})
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), ""))


@require_http_methods(["GET", "POST"])
def hosted_checkout(request, public_id):
    """Local-only hosted checkout simulation; no card or wallet data is collected."""
    if not settings.DEBUG:
        raise Http404
    intent = get_object_or_404(PaymentIntent, public_id=public_id)
    context = {"intent": intent, "amount_pesos": Decimal(intent.amount_centavos) / Decimal(100)}
    if request.method == "POST":
        method = request.POST.get("method", "")
        if method not in PaymentAttempt.Method.values:
            context["error"] = "Choose a simulated payment method."
            return render(request, "simulator/checkout.html", context, status=400)
        try:
            attempt = create_simulated_attempt(intent=intent, method=method, api_key=None)
            complete_simulated_attempt(attempt=attempt, scenario="succeeded", api_key=None)
        except ValidationError as error:
            context["error"] = " ".join(str(value) for value in error.detail.values())
            return render(request, "simulator/checkout.html", context, status=400)
        intent.refresh_from_db()
        if return_url := safe_return_url(intent.return_url, intent):
            return redirect(return_url)
        context.update({"intent": intent, "paid": True, "attempt": attempt})
    return render(request, "simulator/checkout.html", context)
