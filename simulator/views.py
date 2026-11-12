from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiTypes, extend_schema

from payments.models import PaymentAttempt, PaymentIntent
from security.permissions import HasAPIKeyScope
from security.services import enforce_rate_limit
from .serializers import SimulatedAttemptCreateSerializer, SimulatedCompletionSerializer
from .services import complete_simulated_attempt, create_simulated_attempt


class SimulatedAttemptCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]
    required_scope = "payments:write"

    @extend_schema(operation_id="create_simulated_payment_attempt", request=SimulatedAttemptCreateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request, public_id):
        enforce_rate_limit(subject=f"merchant:{request.user.merchant.pk}", action="simulator.attempt.create", limit=30, period_seconds=60)
        try:
            intent = PaymentIntent.objects.get(merchant=request.user.merchant, public_id=public_id)
        except PaymentIntent.DoesNotExist:
            raise NotFound("Payment intent was not found.")
        serializer = SimulatedAttemptCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = create_simulated_attempt(intent=intent, method=serializer.validated_data["method"], api_key=request.auth, request_id=request.headers.get("X-Request-ID", ""))
        return Response({"data": {"attempt_id": str(attempt.reference), "method": attempt.method, "status": attempt.status, "simulation": True}}, status=201)


class SimulatedAttemptCompleteView(APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]
    required_scope = "simulator:write"

    @extend_schema(operation_id="complete_simulated_payment_attempt", request=SimulatedCompletionSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request, reference):
        enforce_rate_limit(subject=f"merchant:{request.user.merchant.pk}", action="simulator.attempt.complete", limit=30, period_seconds=60)
        try:
            attempt = PaymentAttempt.objects.select_related("intent").get(reference=reference, intent__merchant=request.user.merchant)
        except PaymentAttempt.DoesNotExist:
            raise NotFound("Simulated payment attempt was not found.")
        serializer = SimulatedCompletionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        attempt = complete_simulated_attempt(attempt=attempt, scenario=serializer.validated_data["scenario"], api_key=request.auth, request_id=request.headers.get("X-Request-ID", ""))
        return Response({"data": {"attempt_id": str(attempt.reference), "status": attempt.status, "payment_intent_status": attempt.intent.status, "simulation": True}})
