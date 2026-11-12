from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from security.permissions import HasAPIKeyScope
from security.services import audit, enforce_rate_limit
from .models import PaymentIntent
from .serializers import PaymentIntentCreateSerializer, PaymentIntentSerializer
from .services import cancel_payment_intent, create_payment_intent


def _merchant(request):
    return request.user.merchant


def _request_id(request):
    return request.headers.get("X-Request-ID", "")[:64]


class PaymentIntentListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]

    @extend_schema(operation_id="list_payment_intents", responses=PaymentIntentSerializer)
    def get(self, request):
        if not request.auth.has_scope("payments:read"):
            return Response({"error": {"code": "permission_denied", "message": "This API key does not have the required scope."}}, status=403)
        enforce_rate_limit(subject=f"merchant:{_merchant(request).pk}", action="payment_intent.retrieve", limit=120, period_seconds=60)
        intents = PaymentIntent.objects.filter(merchant=_merchant(request)).order_by("-created_at")[:100]
        return Response({"data": PaymentIntentSerializer(intents, many=True).data})

    @extend_schema(operation_id="create_payment_intent", request=PaymentIntentCreateSerializer, responses=PaymentIntentSerializer)
    def post(self, request):
        if not request.auth.has_scope("payments:write"):
            audit(action="payment_intent.create", outcome="denied", merchant=_merchant(request), api_key=request.auth)
            return Response({"error": {"code": "permission_denied", "message": "This API key does not have the required scope."}}, status=403)
        enforce_rate_limit(subject=f"merchant:{_merchant(request).pk}", action="payment_intent.create", limit=30, period_seconds=60)
        idempotency_key = request.headers.get("Idempotency-Key", "")
        if not idempotency_key or len(idempotency_key) > 255:
            raise ValidationError({"Idempotency-Key": ["A header of 1 to 255 characters is required."]})
        serializer = PaymentIntentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, body, http_status, _ = create_payment_intent(
            merchant=_merchant(request), application=request.auth.application, api_key=request.auth,
            data=serializer.validated_data, idempotency_key=idempotency_key, request_id=_request_id(request),
        )
        return Response(body, status=http_status)


class MerchantIntentMixin:
    def get_intent(self, request, public_id):
        try:
            return PaymentIntent.objects.get(merchant=_merchant(request), public_id=public_id)
        except PaymentIntent.DoesNotExist:
            raise NotFound("Payment intent was not found.")


class PaymentIntentDetailView(MerchantIntentMixin, APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]
    required_scope = "payments:read"

    @extend_schema(operation_id="retrieve_payment_intent", responses=PaymentIntentSerializer)
    def get(self, request, public_id):
        enforce_rate_limit(subject=f"merchant:{_merchant(request).pk}", action="payment_intent.retrieve", limit=120, period_seconds=60)
        return Response({"data": PaymentIntentSerializer(self.get_intent(request, public_id)).data})


class PaymentIntentCancelView(MerchantIntentMixin, APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]
    required_scope = "payments:write"

    @extend_schema(operation_id="cancel_payment_intent", request=None, responses=PaymentIntentSerializer)
    def post(self, request, public_id):
        enforce_rate_limit(subject=f"merchant:{_merchant(request).pk}", action="payment_intent.cancel", limit=30, period_seconds=60)
        intent = cancel_payment_intent(intent=self.get_intent(request, public_id), api_key=request.auth, request_id=_request_id(request))
        return Response({"data": PaymentIntentSerializer(intent).data}, status=status.HTTP_200_OK)
