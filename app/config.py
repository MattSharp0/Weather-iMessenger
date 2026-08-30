import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


@dataclass(frozen=True)
class Config:
    sendblue_api_key: str
    sendblue_api_secret: str
    sendblue_signing_secret: str
    sendblue_from_number: str
    db_path: Path
    nws_contact: str
    otp_ttl_minutes: int


def load_config() -> Config:
    return Config(
        sendblue_api_key=_require("SENDBLUE_API_KEY"),
        sendblue_api_secret=_require("SENDBLUE_API_SECRET"),
        sendblue_signing_secret=_require("SENDBLUE_SIGNING_SECRET"),
        sendblue_from_number=_require("SENDBLUE_FROM_NUMBER"),
        db_path=Path(os.environ.get("DB_PATH", "weather_messenger.db")),
        nws_contact=_require("NWS_CONTACT"),
        otp_ttl_minutes=int(os.environ.get("OTP_TTL_MINUTES", "15")),
    )


config = load_config()
