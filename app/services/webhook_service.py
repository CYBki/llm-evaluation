from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import time
from urllib.parse import urlparse

import httpx

from app.config import settings
from app.metrics.definitions import build_evaluation_commentary, get_verdict
from app.models.evaluation import EvaluationResult
from app.models.trace import Trace

logger = logging.getLogger(__name__)

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "db",
        "redis",
        "api",
        "worker",
        "pgadmin",
        "metadata.google.internal",
    }
)


def _is_private_ip(ip_str: str) -> bool:
    """Return True if the IP is loopback, private, link-local, or reserved."""
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
    )


def _validate_webhook_target(url: str) -> bool:
    """Validate that a webhook URL does not point to an internal resource."""
    parsed = urlparse(url)
    hostname = parsed.hostname or ""

    if parsed.scheme != "https":
        logger.warning("SSRF block: non-https scheme in webhook URL %s", url)
        return False

    if hostname.lower() in _BLOCKED_HOSTNAMES:
        logger.warning("SSRF block: blocked hostname in webhook URL %s", url)
        return False

    try:
        addr_infos = socket.getaddrinfo(
            hostname, parsed.port or 443, proto=socket.IPPROTO_TCP
        )
    except socket.gaierror:
        logger.warning("SSRF block: DNS resolution failed for webhook URL %s", url)
        return False

    for family, kind, proto, canonname, sockaddr in addr_infos:
        ip = sockaddr[0]
        if _is_private_ip(ip):
            logger.warning(
                "SSRF block: webhook URL %s resolves to private IP %s",
                url,
                ip,
            )
            return False

    return True


def _build_webhook_payload(trace: Trace, evaluation: EvaluationResult) -> dict:
    """Build the JSON payload sent to the webhook URL."""
    scores = {
        "overall_score": evaluation.overall_score,
        "clarity": evaluation.clarity,
        "coherence": evaluation.coherence,
        "helpfulness": evaluation.helpfulness,
        "completeness": evaluation.completeness,
        "answer_relevancy": evaluation.answer_relevancy,
        "faithfulness": evaluation.faithfulness,
        "hallucination_score": evaluation.hallucination_score,
        "citation_check": evaluation.citation_check,
        "context_precision": evaluation.context_precision,
        "context_recall": evaluation.context_recall,
    }

    verdicts = {
        name: get_verdict(name, value)
        for name, value in scores.items()
        if value is not None
    }

    commentary = build_evaluation_commentary(evaluation.overall_score, scores)

    return {
        "event": "evaluation.completed",
        "trace_id": str(trace.id),
        "status": trace.status,
        "evaluation_duration_ms": evaluation.evaluation_duration_ms,
        "scores": scores,
        "verdicts": verdicts,
        "flags": {
            "is_off_topic": evaluation.is_off_topic,
            "is_deflection": evaluation.is_deflection,
        },
        "details": {
            "hallucination_claims": evaluation.hallucination_claims or [],
            "completeness_key_points": evaluation.completeness_key_points or [],
        },
        "reasoning_summary": evaluation.reasoning_summary,
        "evaluation_commentary": commentary,
        "cost_usd": evaluation.cost_usd,
        "total_tokens": evaluation.total_tokens,
    }


def _sign_payload(payload_bytes: bytes) -> str:
    """HMAC-SHA256 signature for webhook payload verification."""
    return hmac.new(
        settings.webhook_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


def deliver_webhook(trace: Trace, evaluation: EvaluationResult) -> None:
    """POST evaluation results to the trace's webhook_url with retries."""
    url = trace.webhook_url
    if not url:
        return

    if not _validate_webhook_target(url):
        logger.error(
            "Webhook delivery blocked (SSRF) for trace %s → %s",
            trace.id,
            url,
        )
        return

    payload = _build_webhook_payload(trace, evaluation)
    body = json.dumps(payload, default=str).encode("utf-8")

    headers = {"Content-Type": "application/json"}
    if settings.webhook_secret:
        headers["X-Signature-SHA256"] = _sign_payload(body)

    max_retries = settings.webhook_max_retries
    timeout = settings.webhook_timeout_seconds

    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(url, content=body, headers=headers)
            if resp.status_code < 400:
                logger.info(
                    "Webhook delivered for trace %s → %s (status=%d)",
                    trace.id,
                    url,
                    resp.status_code,
                )
                return
            logger.warning(
                "Webhook attempt %d/%d failed for trace %s → %s (status=%d)",
                attempt,
                max_retries,
                trace.id,
                url,
                resp.status_code,
            )
        except Exception:
            logger.warning(
                "Webhook attempt %d/%d error for trace %s → %s",
                attempt,
                max_retries,
                trace.id,
                url,
                exc_info=True,
            )

        if attempt < max_retries:
            time.sleep(2 ** (attempt - 1))

    logger.error(
        "Webhook delivery failed after %d attempts for trace %s", max_retries, trace.id
    )
