# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

An iMessage bot: text coordinates (`lat,lon`), get a short weather forecast back — including over Apple's satellite messaging when off-grid. Single-tenant, personal-scale project: one admin (controlled via the local CLI), a handful of pre-approved phone numbers, no self-serve signup. Don't add multi-tenancy, user accounts, or scale-oriented infrastructure unless explicitly asked — the simplicity (raw `sqlite3`, no ORM, no rate limiting, no queueing) is intentional for this scale, not an oversight.

## Commands

```bash
uv sync                                    # install dependencies
uv run pytest                              # run all tests
uv run pytest tests/test_parsing.py::test_comma_separated   # run a single test
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000       # run the server locally
uv run python cli.py <command>             # admin CLI — see cli.py or README for subcommands
uv run python scripts/simulate_webhook.py --from +1555... --text "lat,lon [option]"  # simulate an inbound webhook against a local server, see README
```

No linter/formatter is configured. No build step — this isn't packaged/distributed.

## Architecture

**Request flow:** iPhone (iMessage, possibly via satellite) → Sendblue (third-party iMessage transport — Apple has no public API for sending iMessages) → Cloudflare Tunnel → FastAPI webhook (`app/main.py`, the only public route) → SQLite → weather API → reply sent back via Sendblue.

**Two-layer, both-admin-driven verification — no verification logic lives in the webhook:**
1. Sendblue's own contact opt-in (`sendblue.create_contact`) — required by Sendblue before *any* message can be sent to a number, including this app's own OTP. This is inbound-first: the recipient has to text `SENDBLUE_FROM_NUMBER` themselves before Sendblue considers them opted in — there's no API call that makes Sendblue text them first (found the hard way: Sendblue's own `/v2/contacts/verify` endpoint just returns "no contact found" until the recipient has already texted in, at which point it's a no-op — so this app doesn't call it at all). This app has no visibility into that inbound text; it's entirely Sendblue-side.
2. This app's own OTP, issued and checked via `cli.py verify-number` — the admin runs it, reads the code off whichever phone it landed on, and types it into the CLI (2FA-style), rather than the number replying via iMessage. This is deliberate: the security property being protected is "only whoever can run this CLI can add/verify numbers," which CLI-local-access enforces directly. Don't reintroduce webhook-based OTP verification without understanding this was a considered change (see git history / the plan doc), not an oversight.

The webhook (`app/main.py`) therefore only ever *serves* already-verified numbers. Unregistered and unverified numbers are both silently ignored (no reply) — this is intentional so the endpoint's existence and verification-state aren't observable from the outside.

**Weather lookup** (`app/weather.py`): NWS `api.weather.gov` first (US coordinates, includes active alerts, requires a descriptive `User-Agent` per `NWS_CONTACT` or NWS 403s), falling back to Open-Meteo (global, no key) when NWS doesn't cover the point. Both normalize to a short text summary — replies are kept well under Apple's satellite-messaging-friendly length (300 chars, enforced by `_truncate`).

The incoming text can carry an optional trailing forecast option word, parsed by `parsing.parse_request()` (default/`forecast`/`tonight`/`tomorrow`; an unrecognized word makes the whole message invalid rather than silently falling back). The option only affects the NWS path — `_select_period()` picks the relevant period (`tonight` matches by name with a not-daytime fallback; `tomorrow` matches the next day's date against period `startTime` rather than assuming a fixed index, since which period is "tomorrow" shifts depending on time of day) and `get_forecast()` builds either the full `detailedForecast` (default/tonight/tomorrow) or a compact 3-period summary via `_period_line()`/`_period_summary()` (`forecast`). Open-Meteo ignores the option entirely and always returns its normal current-conditions summary — its response shape isn't set up to support per-period selection, and that was an explicit scope cut rather than an oversight.

Because a `detailedForecast` (plus an active-alert prefix) can exceed 300 chars, `_try_nws()` falls back to the short compiled `_period_line()` form for that same period rather than splitting the reply across multiple messages — again, a deliberate simplicity choice for this scale, not a limitation to fix. `_shorten()` (case-insensitive `and` → `&`) is applied to both `shortForecast` and `detailedForecast` to buy back characters; don't assume NWS text is always Title Case when matching against it elsewhere.

**Sendblue quirks baked into `app/sendblue.py`** (found the hard way, not documented consistently by Sendblue): `from_number` is required on every send call even on the free/shared tier; a contact must be created *and* opted in before it can receive anything; incoming webhook payload field names are inconsistent across Sendblue's own docs, so `extract_incoming()` defensively checks both `from_number`/`number` and `content`/`text`; real API calls can take ~20s, hence the 45s timeout on `send_message`.

**Security specifics:** webhook requests are rejected via constant-time HMAC compare of `SENDBLUE_SIGNING_SECRET` before the body is even parsed; OTP codes are HMAC-SHA256 hashed with a dedicated `OTP_PEPPER` (not bare-hashed — a 6-digit code is only 1M values, cheap to precompute against an unkeyed hash); FastAPI's auto-docs (`/docs`, `/redoc`, `/openapi.json`) are explicitly disabled since those routes would bypass the webhook's own auth entirely.

**Schema** (`schema.sql`): `phone_numbers`, `otp_codes` (deliberately separate from `phone_numbers` so re-issuing a code doesn't touch the phone row), `messages` (full inbound/outbound audit log with parsed coordinates).

**Deployment reality — this runs on a first-generation Raspberry Pi Zero (ARMv6), which drives several non-obvious constraints:**
- `requires-python = ">=3.11"`, not an exact/tighter pin — `uv`'s managed Python downloads have no ARMv6 build, so this must resolve against the system interpreter.
- `uvicorn` has no `[standard]` extras — `uvloop`/`httptools` are C extensions with no ARMv6 wheels, forcing slow/risky source compiles on 512MB single-core hardware for zero benefit at this traffic volume.
- `pydantic-core` (a `fastapi`/`pydantic` dependency, Rust-based) has no ARMv6 wheel on PyPI either. The working fix is Pi-local and *not* committed to this repo: `uv lock --default-index https://www.piwheels.org/simple` run directly on the Pi when a fresh `.venv` build is needed there. Multiple attempts to make `uv` prefer piwheels for just this one package without disturbing the PyPI/macOS-compatible lockfile (`--default-index` globally, `[tool.uv.sources]` explicit-index pinning) did not work as documented — don't re-attempt those exact approaches without re-verifying against current `uv` behavior first.
- The production systemd unit's `ExecStart` points directly at `.venv/bin/uvicorn`, never `uv run` — `uv run` re-validates the venv against `uv.lock` on every invocation, which turns a routine service restart into a surprise dependency rebuild (a real problem when a dependency has no wheel for the platform).
- Cloudflare's Bot Fight Mode silently dropped Sendblue's webhook POSTs in production while manual `curl` testing kept working fine — worth remembering as a debugging lead if the webhook ever appears to receive nothing despite Sendblue showing message delivery on their end.

## Testing

Only `tests/test_parsing.py` (coordinate parsing) is automated. The webhook flow, OTP verification, and weather lookups have been validated end-to-end in production against real Sendblue/iMessage traffic and live weather APIs, but not captured as automated tests — treat that as a gap, not as evidence the logic is untested.
