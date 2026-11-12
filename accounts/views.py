from django.contrib.auth import authenticate, login, logout
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import OpenApiTypes, extend_schema

from security.services import audit, enforce_rate_limit
from .serializers import LoginSerializer


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(operation_id="login", request=LoginSerializer, responses=OpenApiTypes.OBJECT)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        username = serializer.validated_data["username"]
        enforce_rate_limit(subject=f"login:{username.casefold()}", action="login", limit=5, period_seconds=900)
        user = authenticate(request, username=username, password=serializer.validated_data["password"])
        if user is None or not user.is_active:
            audit(action="login", outcome="denied", metadata={"username": username[:150]})
            raise AuthenticationFailed("Invalid username or password.")
        login(request, user)
        audit(action="login", outcome="success", metadata={"user_id": user.pk})
        return Response({"data": {"username": user.username, "role": user.role}})


class LogoutView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(operation_id="logout", request=None, responses={204: None})
    def post(self, request):
        audit(action="logout", outcome="success", metadata={"user_id": request.user.pk})
        logout(request)
        return Response(status=204)
