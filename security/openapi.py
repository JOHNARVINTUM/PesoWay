from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ScopedAPIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "security.authentication.ScopedAPIKeyAuthentication"
    name = "BearerApiKey"

    def get_security_definition(self, auto_schema):
        return {"type": "http", "scheme": "bearer", "bearerFormat": "PesoWay API key"}
