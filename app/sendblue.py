import hmac

import httpx

from app.config import config

API_BASE = "https://api.sendblue.co/api"


class SendblueError(RuntimeError):
    pass


def _post(path: str, json: dict) -> dict:
    response = httpx.post(
        f"{API_BASE}{path}",
        json=json,
        headers={
            "sb-api-key-id": config.sendblue_api_key,
            "sb-api-secret-key": config.sendblue_api_secret,
        },
        timeout=45,
    )
    data = response.json()
    if response.status_code >= 400 or data.get("status") == "ERROR":
        raise SendblueError(data.get("error_message") or data.get("message") or response.text)
    return data


def send_message(to_number: str, content: str) -> None:
    _post(
        "/send-message",
        {"number": to_number, "content": content, "from_number": config.sendblue_from_number},
    )


def create_contact(number: str) -> None:
    """Register `number` as a Sendblue contact. Required before it can be messaged at all."""
    _post("/v2/contacts", {"number": number})


def request_contact_verification(number: str) -> None:
    """Trigger Sendblue's own opt-in verification text to `number`.

    The recipient must respond to that message before Sendblue will allow any
    further messages to them (including our own OTP) — separate from and
    prior to this app's own OTP verification step.
    """
    _post("/v2/contacts/verify", {"number": number})


def verify_signature(header_secret: str | None) -> bool:
    if header_secret is None:
        return False
    return hmac.compare_digest(header_secret, config.sendblue_signing_secret)


def extract_incoming(payload: dict) -> tuple[str | None, str | None]:
    """Pull (sender_number, content) out of a Sendblue 'receive' webhook payload.

    NOTE: Sendblue's published field names have varied across their docs/blog
    examples (from_number vs number). This checks both. On the first real
    webhook delivery, log the raw payload and confirm/simplify this.
    """
    sender = payload.get("from_number") or payload.get("number")
    content = payload.get("content") or payload.get("text")
    return sender, content
