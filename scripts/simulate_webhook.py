"""Simulate an inbound Sendblue webhook POST against a locally running app.

Exercises the full pipeline (signature check -> parsing -> weather lookup ->
outbound Sendblue send -> DB logging) without touching the Pi or Sendblue's
webhook configuration. The outbound reply is a REAL Sendblue send to
--from, so use a real number you can read texts on.

Prereqs:
  - `uv run uvicorn app.main:app --port 8000` running in another terminal
  - --from already registered *and verified* in your local DB:
      uv run python cli.py add-number +15551234567
      uv run python cli.py verify-number +15551234567
    (these hit the real Sendblue API)

Usage:
  uv run python scripts/simulate_webhook.py --from +15551234567 --text "47.6062,-122.3321 tonight"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

from app.config import config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--from",
        dest="from_number",
        required=True,
        help="Sender number, E.164 (must be verified in your local DB)",
    )
    parser.add_argument(
        "--text",
        default="47.6062,-122.3321",
        help="Message body, e.g. '47.6062,-122.3321 forecast' (default: plain coordinates)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost:8000/webhook/sendblue",
        help="Webhook endpoint to POST to (default: local server on port 8000)",
    )
    args = parser.parse_args()

    payload = {"from_number": args.from_number, "content": args.text}
    headers = {"sb-signing-secret": config.sendblue_signing_secret}

    response = httpx.post(args.url, json=payload, headers=headers, timeout=45)
    print(f"{response.status_code} {response.text or '(empty body)'}")


if __name__ == "__main__":
    main()
