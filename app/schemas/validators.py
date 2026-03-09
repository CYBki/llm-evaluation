from __future__ import annotations

from urllib.parse import urlparse


def validate_https_webhook_url(value: str | None) -> str | None:
    """Validate shared webhook URL rules for ingest schemas."""
    if value is None:
        return value

    parsed = urlparse(value)
    if parsed.scheme != "https":
        raise ValueError("webhook_url must use https:// scheme")
    if not parsed.hostname:
        raise ValueError("webhook_url must contain a valid hostname")

    hostname = parsed.hostname
    if hostname.replace(".", "").isdigit() or ":" in hostname:
        raise ValueError("webhook_url must use a domain name, not an IP address")
    if "." not in hostname:
        raise ValueError("webhook_url must be a fully qualified domain name")

    return value
