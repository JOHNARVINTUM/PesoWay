from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiTypes, extend_schema

from security.permissions import HasAPIKeyScope
from security.services import audit, enforce_rate_limit
from .models import WebhookEndpoint
from .models import WebhookEvent
from .serializers import WebhookEndpointCreateSerializer


class WebhookEndpointListCreateView(APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]
    required_scope = "webhooks:write"

    @extend_schema(operation_id="create_webhook_endpoint", request=WebhookEndpointCreateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        enforce_rate_limit(subject=f"merchant:{request.user.merchant.pk}", action="webhook.manage", limit=20, period_seconds=3600)
        serializer = WebhookEndpointCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        endpoint, secret = WebhookEndpoint.create_secret(merchant=request.user.merchant, **serializer.validated_data)
        audit(action="webhook_endpoint.create", outcome="success", merchant=request.user.merchant, api_key=request.auth, metadata={"endpoint": endpoint.pk})
        return Response({"data": {"id": endpoint.pk, "url": endpoint.url, "subscribed_events": endpoint.subscribed_events, "secret": secret}}, status=201)


class WebhookEventListView(APIView):
    permission_classes = [IsAuthenticated, HasAPIKeyScope]
    required_scope = "webhooks:read"

    @extend_schema(operation_id="list_webhook_events", responses=OpenApiTypes.OBJECT)
    def get(self, request):
        enforce_rate_limit(subject=f"merchant:{request.user.merchant.pk}", action="webhook.events", limit=120, period_seconds=60)
        events = WebhookEvent.objects.filter(merchant=request.user.merchant).order_by("-created_at")[:100]
        return Response({"data": [{
            "id": str(event.public_id), "type": event.event_type, "data": event.payload,
            "created_at": event.created_at.isoformat(),
            "deliveries": [{"status": delivery.status, "attempt_count": delivery.attempt_count, "last_status_code": delivery.last_status_code}
                           for delivery in event.deliveries.all()],
        } for event in events]})
