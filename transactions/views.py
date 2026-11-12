from django.db import transaction
from django.db.models import Sum
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from payments.models import PaymentIntent
from security.permissions import HasAPIKeyScope
from security.services import audit, enforce_rate_limit
from .models import LedgerEntry, Refund
from .serializers import LedgerEntrySerializer, RefundCreateSerializer, RefundSerializer
from .services import record_entry


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]
    required_scope = "transactions:read"

    @extend_schema(operation_id="list_transactions", responses=LedgerEntrySerializer)
    def get(self, request):
        enforce_rate_limit(subject=f"merchant:{request.user.merchant.pk}", action="transactions.retrieve", limit=120, period_seconds=60)
        entries = LedgerEntry.objects.filter(merchant=request.user.merchant).order_by("-created_at")[:100]
        return Response({"data": LedgerEntrySerializer(entries, many=True).data})


class RefundCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]
    required_scope = "refunds:write"

    @extend_schema(operation_id="create_refund", request=RefundCreateSerializer, responses=RefundSerializer)
    def post(self, request):
        enforce_rate_limit(subject=f"merchant:{request.user.merchant.pk}", action="refund.create", limit=10, period_seconds=3600)
        serializer = RefundCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            try:
                intent = PaymentIntent.objects.select_for_update().get(merchant=request.user.merchant, public_id=serializer.validated_data["payment_intent_id"])
            except PaymentIntent.DoesNotExist:
                raise NotFound("Payment intent was not found.")
            if intent.status != PaymentIntent.Status.SUCCEEDED:
                raise ValidationError({"payment_intent_id": ["Only succeeded payment intents may be refunded."]})
            amount = serializer.validated_data["amount_centavos"]
            refunded = Refund.objects.filter(payment_intent=intent).aggregate(total=Sum("amount_centavos"))["total"] or 0
            if amount + refunded > intent.amount_centavos:
                raise ValidationError({"amount_centavos": ["Refund amount exceeds the unrefunded payment amount."]})
            refund = Refund.objects.create(merchant=request.user.merchant, payment_intent=intent, amount_centavos=amount, merchant_reference=serializer.validated_data["merchant_reference"])
            record_entry(merchant=intent.merchant, payment_intent=intent, entry_type=LedgerEntry.EntryType.REFUND, amount_centavos=-amount, reference=f"refund-{refund.public_id}", metadata={"refund": str(refund.public_id)})
            audit(action="refund.create", outcome="success", merchant=intent.merchant, api_key=request.auth, metadata={"refund": str(refund.public_id)})
        return Response({"data": RefundSerializer(refund).data}, status=201)
