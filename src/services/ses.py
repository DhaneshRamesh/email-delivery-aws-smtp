"""AWS SES helper functions."""
from __future__ import annotations

from typing import Optional

try:  # pragma: no cover - optional dependency import
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # pragma: no cover
    boto3 = None  # type: ignore

    class BotoCoreError(Exception):
        """Fallback exception when botocore is unavailable."""

    class ClientError(Exception):
        """Fallback exception when botocore is unavailable."""

from src.core.config import settings
from src.utils.logger import logger


class SESService:
    """Encapsulates the boto3 SES client."""

    def __init__(
        self,
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        region_name: str | None = None,
    ) -> None:
        self.aws_access_key_id = aws_access_key_id or settings.aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key or settings.aws_secret_access_key
        self.region_name = region_name or settings.aws_region_name
        self._client = None

    def _client_or_raise(self):
        if self._client is None:
            if boto3 is None:  # pragma: no cover - dependency notice
                raise RuntimeError("boto3 is required for SES operations. Install project dependencies.")
            if not self.region_name:
                raise RuntimeError("AWS region is required for SES. Set AWS_REGION_NAME in the environment.")

            client_kwargs = {"region_name": self.region_name}
            if self.aws_access_key_id and self.aws_secret_access_key:
                client_kwargs["aws_access_key_id"] = self.aws_access_key_id
                client_kwargs["aws_secret_access_key"] = self.aws_secret_access_key

            self._client = boto3.client("ses", **client_kwargs)
        return self._client

    def send_email(
        self,
        *,
        subject: str,
        recipient: str,
        text_body: str,
        html_body: Optional[str] = None,
        sender: Optional[str] = None,
    ) -> str:
        """Send an email and return the SES message ID."""

        client = self._client_or_raise()
        try:
            response = client.send_email(
                Source=sender or settings.ses_sender_email,
                Destination={"ToAddresses": [recipient]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {
                        "Text": {"Data": text_body},
                        "Html": {"Data": html_body or text_body},
                    },
                },
            )
        except (BotoCoreError, ClientError) as exc:  # pragma: no cover - network service
            logger.exception("Failed to send email via SES")
            raise RuntimeError("SES send_email failed") from exc

        message_id = response.get("MessageId", "")
        logger.info("SES send_email message_id=%s", message_id)
        return message_id


ses_service = SESService()
