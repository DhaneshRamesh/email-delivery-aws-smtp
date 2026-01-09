"""SNS helper utilities for signature verification and subscriptions."""
from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from src.utils.logger import logger


def is_allowed_cert_url(cert_url: str) -> tuple[bool, str]:
    """Validate SNS SigningCertURL host and path."""
    parsed = urlparse(cert_url)
    if parsed.scheme != "https":
        return False, "SigningCertURL must use https"
    if not parsed.hostname:
        return False, "SigningCertURL missing hostname"
    host = parsed.hostname
    if host != "sns.amazonaws.com" and not (host.startswith("sns.") and host.endswith(".amazonaws.com")):
        return False, "SigningCertURL hostname is not allowed"
    if not parsed.path.startswith("/SimpleNotificationService-"):
        return False, "SigningCertURL path is not allowed"
    return True, "ok"


def _build_string_to_sign(payload: dict[str, Any]) -> str:
    message_type = payload.get("Type")
    if message_type == "Notification":
        fields = ["Message", "MessageId", "Subject", "Timestamp", "TopicArn", "Type"]
    else:
        fields = ["Message", "MessageId", "SubscribeURL", "Timestamp", "Token", "TopicArn", "Type"]

    parts: list[str] = []
    for field in fields:
        value = payload.get(field)
        if value is None:
            continue
        parts.append(field)
        parts.append(str(value))
    return "\n".join(parts) + "\n"


def _fetch_url(url: str, timeout_seconds: int) -> bytes:
    request = Request(url, method="GET")
    with urlopen(request, timeout=timeout_seconds) as response:
        return response.read()


def _run_openssl(args: list[str], input_bytes: bytes | None, timeout_seconds: int) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        input=input_bytes,
        capture_output=True,
        check=False,
        timeout=timeout_seconds,
    )


def verify_sns_signature(payload: dict[str, Any], timeout_seconds: int) -> tuple[bool, str]:
    """Verify SNS signature using the SigningCertURL."""
    signature_b64 = payload.get("Signature")
    cert_url = payload.get("SigningCertURL")
    signature_version = payload.get("SignatureVersion")
    if str(signature_version) != "1":
        return False, "Unsupported SignatureVersion"
    if not signature_b64 or not cert_url:
        return False, "Missing Signature or SigningCertURL"

    allowed, reason = is_allowed_cert_url(cert_url)
    if not allowed:
        return False, reason

    try:
        cert_pem = _fetch_url(cert_url, timeout_seconds)
    except Exception as exc:  # pragma: no cover - network errors
        logger.warning("Failed to fetch SNS cert: %s", exc)
        return False, "Failed to fetch SigningCertURL"

    try:
        signature = base64.b64decode(signature_b64)
    except Exception:
        return False, "Invalid Signature encoding"

    data_to_sign = _build_string_to_sign(payload).encode("utf-8")

    try:
        with tempfile.NamedTemporaryFile() as cert_file, tempfile.NamedTemporaryFile() as pubkey_file, tempfile.NamedTemporaryFile() as data_file, tempfile.NamedTemporaryFile() as sig_file:
            cert_file.write(cert_pem)
            cert_file.flush()
            pubkey_result = _run_openssl(
                ["openssl", "x509", "-pubkey", "-noout", "-in", cert_file.name],
                input_bytes=None,
                timeout_seconds=timeout_seconds,
            )
            if pubkey_result.returncode != 0:
                return False, "Failed to extract public key"
            pubkey_file.write(pubkey_result.stdout)
            pubkey_file.flush()

            data_file.write(data_to_sign)
            data_file.flush()
            sig_file.write(signature)
            sig_file.flush()

            verify_result = _run_openssl(
                ["openssl", "dgst", "-sha1", "-verify", pubkey_file.name, "-signature", sig_file.name, data_file.name],
                input_bytes=None,
                timeout_seconds=timeout_seconds,
            )
            if verify_result.returncode != 0:
                return False, "Signature verification failed"
    except FileNotFoundError:
        return False, "openssl is not available for signature verification"
    except Exception:
        return False, "Signature verification error"

    return True, "ok"


def confirm_subscription(subscribe_url: str, timeout_seconds: int) -> bool:
    try:
        _fetch_url(subscribe_url, timeout_seconds)
        return True
    except Exception as exc:  # pragma: no cover - network errors
        logger.warning("Failed to confirm SNS subscription: %s", exc)
        return False


def dumps_payload(payload: dict[str, Any], max_bytes: int = 32768) -> str:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
    if len(raw) > max_bytes:
        return raw[:max_bytes]
    return raw
