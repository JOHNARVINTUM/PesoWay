from rest_framework import authentication, exceptions
from merchants.models import APIKey


class APIKeyPrincipal:
    """Small authenticated principal exposed to API-key protected views."""
    is_authenticated = True

    def __init__(self, key: APIKey) -> None:
        self.api_key = key
        self.merchant = key.application.merchant


class ScopedAPIKeyAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate_header(self, request):
        return self.keyword

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("latin-1")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            raise exceptions.AuthenticationFailed("Invalid authorization header.")
        key = APIKey.authenticate(parts[1])
        if key is None:
            raise exceptions.AuthenticationFailed("Invalid API key.")
        return APIKeyPrincipal(key), key

