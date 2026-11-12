import ipaddress
import socket
from urllib.parse import urlparse

from django.core.exceptions import ValidationError


def validate_webhook_url(value: str) -> None:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise ValidationError("Webhook URLs must be absolute HTTPS URLs without credentials.")
    try:
        addresses = {result[4][0] for result in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as error:
        raise ValidationError("Webhook host could not be resolved.") from error
    for address in addresses:
        ip = ipaddress.ip_address(address)
        if not ip.is_global:
            raise ValidationError("Webhook host must resolve only to globally routable addresses.")
