from rest_framework.permissions import BasePermission


class HasAPIKeyScope(BasePermission):
    """Views declare ``required_scope`` to guard individual operations."""
    message = "This API key does not have the required scope."

    def has_permission(self, request, view):
        required_scope = getattr(view, "required_scope", None)
        if required_scope is None:
            return True
        return bool(getattr(request.auth, "has_scope", lambda _scope: False)(required_scope))

