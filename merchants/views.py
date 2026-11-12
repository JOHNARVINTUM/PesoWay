from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiTypes, extend_schema

from security.services import audit, enforce_rate_limit
from .models import APIKey, Application
from .serializers import APIKeyCreateSerializer


class MerchantOwnerMixin:
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def application(self, request, application_id):
        try:
            return Application.objects.get(pk=application_id, merchant__owner=request.user, merchant__is_active=True)
        except Application.DoesNotExist:
            raise NotFound("Application was not found.")


class APIKeyCreateView(MerchantOwnerMixin, APIView):
    @extend_schema(operation_id="create_merchant_api_key", request=APIKeyCreateSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        enforce_rate_limit(subject=f"user:{request.user.pk}", action="api_key.create", limit=5, period_seconds=3600)
        serializer = APIKeyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        application = self.application(request, serializer.validated_data["application_id"])
        key, raw_key = APIKey.create_secret(application=application, scopes=serializer.validated_data["scopes"])
        audit(action="api_key.create", outcome="success", merchant=application.merchant, api_key=key, metadata={"api_key": key.prefix})
        return Response({"data": {"id": key.pk, "prefix": key.prefix, "scopes": key.scopes, "secret": raw_key}}, status=201)


class APIKeyRevokeView(MerchantOwnerMixin, APIView):
    @extend_schema(operation_id="revoke_merchant_api_key", request=None, responses={204: None})
    def post(self, request, key_id):
        try:
            key = APIKey.objects.select_related("application__merchant").get(pk=key_id, application__merchant__owner=request.user)
        except APIKey.DoesNotExist:
            raise NotFound("API key was not found.")
        key.revoke()
        audit(action="api_key.revoke", outcome="success", merchant=key.application.merchant, api_key=key, metadata={"api_key": key.prefix})
        return Response(status=204)
