import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from app.config import config


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def generate_code() -> tuple[str, str, str]:
    """Returns (plaintext_code, code_hash, expires_at_iso)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=config.otp_ttl_minutes)
    return code, _hash_code(code), expires_at.isoformat(sep=" ", timespec="seconds")


def matches(candidate: str, code_hash: str) -> bool:
    return secrets.compare_digest(_hash_code(candidate.strip()), code_hash)
