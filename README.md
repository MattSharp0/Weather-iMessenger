# Weather-Messenger

Text your coordinates via iMessage (including over satellite, when off-grid) and get a short weather forecast back. Built for personal use — a handful of pre-approved numbers, no public signup or self-serve onboarding.

## Prerequisites

- Python 3.12+ and [`uv`](https://docs.astral.sh/uv/)
- A [Sendblue](https://sendblue.com) account (see "Why Sendblue" below) — the free tier works fine at this scale
- Somewhere to run this that's reachable from the internet for the Sendblue webhook. A [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) is the easiest no-port-forwarding option; a *named* tunnel (for a stable URL) needs a domain added to your Cloudflare account. A quick/anonymous tunnel works for initial testing but gets a new random URL on every restart and isn't reliable long-term — don't use it as your permanent webhook target.

## Setup

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Copy the env template and fill in real values:

   ```bash
   cp .env.example .env
   ```

   | Variable | Description |
   |---|---|
   | `SENDBLUE_API_KEY` / `SENDBLUE_API_SECRET` | From your Sendblue account (used to send messages) |
   | `SENDBLUE_SIGNING_SECRET` | Shared secret you set in the Sendblue webhook config, checked on every incoming request |
   | `SENDBLUE_FROM_NUMBER` | Required on every send, even on the free/shared tier. Find yours via `GET https://api.sendblue.co/api/lines` with your API key/secret headers — it returns `{"numbers": ["+1..."]}` |
   | `OTP_PEPPER` | Secret key used to HMAC-hash OTP codes before storing them. Generate one with `python3 -c "import secrets; print(secrets.token_hex(32))"` — treat it like any other secret, never reuse a value from an example. |
   | `DB_PATH` | Path to the SQLite file (default `weather_messenger.db`) |
   | `NWS_CONTACT` | Your email, sent as part of the required `User-Agent` on NWS API calls |
   | `OTP_TTL_MINUTES` | How long a verification code stays valid (default 15) |

3. Create the database:

   ```bash
   uv run python cli.py init-db
   ```

4. Register yourself (and anyone else). This is two steps, because Sendblue itself gates messaging behind its own opt-in — separate from and prior to this app's own OTP check:

   ```bash
   uv run python cli.py add-number +15551234567 --label me
   ```

   This creates the Sendblue contact and triggers *Sendblue's own* opt-in verification text to that number. Reply to that text first — until Sendblue considers the number opted in, it will reject anything we try to send it, including our own code. Once that's confirmed:

   ```bash
   uv run python cli.py verify-number +15551234567
   ```

   This sends this app's own verification code and then prompts you for it right there in the terminal — like entering a 2FA code — rather than requiring a reply over iMessage. Read the code off whichever phone it landed on and type it in (3 attempts against that code before it asks you to re-run for a fresh one). Verification only completes once you enter it correctly; the number can't trigger weather lookups until then. If you jump ahead and run `verify-number` before the Sendblue opt-in is confirmed, it fails with a clear message telling you to wait/retry `add-number` rather than crashing.

5. Run the server:

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```

   Point your Sendblue "receive" webhook at wherever this is publicly reachable (e.g. a Cloudflare Tunnel), path `/webhook/sendblue`.

## CLI usage

The CLI is admin-only tooling — run it locally, never expose it to the network.

```bash
uv run python cli.py init-db                             # create the SQLite DB from schema.sql
uv run python cli.py add-number +15551234567 --label me  # register a number, trigger Sendblue's opt-in text
uv run python cli.py verify-number +15551234567            # send this app's OTP, prompt for it inline (2FA-style)
uv run python cli.py list-numbers                          # list all registered numbers + status
uv run python cli.py revoke +15551234567                    # flip a number back to unverified
```

## How it works

**Verification (one-time per number, two layers, both admin-driven — no verification happens over the webhook):**
1. You run `add-number` for a number you trust → row inserted, Sendblue contact created, Sendblue's own opt-in text sent.
2. They reply to *that* text (per Sendblue's own flow — this app has no visibility into it).
3. You run `verify-number` → this app's own OTP iMessage is sent, and the CLI prompts you for it right there in the terminal. You type in whatever code landed on the phone; a match flips the number to verified in our DB. This is deliberately not "reply via iMessage" — the property this step protects is "only whoever can run this CLI can add/verify numbers," which is enforced by CLI access (already local-only), not by who can text back from a given number.

**Regular usage:**
1. A verified number texts coordinates, e.g. `47.6062,-122.3321`.
2. The webhook parses them, fetches a forecast, and texts a short summary back.
3. Anything from an unregistered number is silently ignored — the bot never reveals it exists to a random text.

## Design

```
iPhone (satellite) ⇄ iMessage ⇄ Sendblue ⇄ [Cloudflare Tunnel] ⇄ FastAPI app ⇄ SQLite
                                                                       ⇓
                                                      NWS api.weather.gov (US) or
                                                      Open-Meteo (fallback, global)
```

**Why Sendblue:** Apple has no public API for sending iMessages, and Apple Messages for Business can't send the first message — a non-starter for an inbound-triggered bot. Sendblue is a third-party iMessage transport that fits a personal-scale project. Satellite messaging only carries plain text (no rich attachments), so coordinates have to come in as typed text like `lat,lon` — that's the only input format this supports.

**Modules** (`app/`):
| File | Responsibility |
|---|---|
| `main.py` | FastAPI app; the one public route, `POST /webhook/sendblue` |
| `sendblue.py` | Sending messages, Sendblue contact creation/opt-in, webhook signature verification, payload parsing |
| `weather.py` | `get_forecast(lat, lon)` — tries NWS first (US, includes active alerts), falls back to Open-Meteo (global, no key) |
| `parsing.py` | Coordinate parsing (`lat,lon` or `lat lon`, decimal degrees, range-checked) |
| `otp.py` | 6-digit code generation, hashing, constant-time comparison |
| `db.py` | Thin `sqlite3` wrapper — no ORM, this is small enough not to need one |
| `config.py` | Loads and validates `.env` |

**Schema** (`schema.sql`): three tables — `phone_numbers` (who's allowed to use this), `otp_codes` (verification codes, kept separate so re-issuing one doesn't touch the phone row), `messages` (full inbound/outbound log, including parsed coordinates, for history/debugging).

**Security:**
- Every webhook request is checked against `SENDBLUE_SIGNING_SECRET` (constant-time compare) — the only auth gating the public endpoint. It's rejected before the body is even parsed.
- OTPs are stored as HMAC-SHA256 hashes keyed with `OTP_PEPPER` (not bare hashes — a 6-digit code is only 1M possible values, cheap to precompute against an unkeyed hash if the DB file ever leaked), expire in 15 minutes, and are single-use.
- Verification is entirely CLI-side (`verify-number`) — the public webhook never verifies a number, it only serves already-verified ones. Unregistered *and* unverified numbers both get silently ignored, so the endpoint doesn't leak that it exists or hint at its verification state.
- FastAPI's auto-generated docs (`/docs`, `/redoc`, `/openapi.json`) are disabled — they're separate routes that would otherwise bypass the webhook's own auth and expose the API schema to anyone who finds the URL.
- All DB writes use parameterized queries; nothing user-supplied is ever interpolated into SQL.

**Limitations (know these before self-hosting):**
- No rate limiting on the webhook. In practice it's gated by the shared signing secret (Sendblue is the only party that can produce a valid one) rather than app-level throttling — acceptable for a personal-scale bot, not for anything higher-traffic.
- Single-tenant by design: there's no user/org model, just a flat list of phone numbers one admin controls via the CLI. Don't expose the CLI or the SQLite file to anyone you don't want able to add/revoke numbers.
- `.env` and the SQLite file (which contains phone numbers and OTP hashes) aren't given special filesystem permissions beyond your umask — `chmod 600` both if you're on a shared machine.
- MIT licensed — see [LICENSE](LICENSE).

**Known open item:** Sendblue's own docs/blog examples disagree on the exact *incoming webhook* payload field names (`from_number` vs `number`). `sendblue.extract_incoming()` checks both, but this should be confirmed against your first real incoming webhook — worth logging the raw payload once and double-checking. (Separately, on the *outgoing* send call, `from_number` turned out to be required even on the free/shared tier despite docs suggesting otherwise — already fixed, see `SENDBLUE_FROM_NUMBER` above. Also note real Sendblue API calls can take ~20s, so `sendblue.send_message()` uses a 45s timeout, not a short one.)

## Deployment notes

- Designed to run on a home server/Pi behind a Cloudflare Tunnel (no inbound ports opened, TLS handled by Cloudflare).
- Run under systemd so it survives a reboot; point the unit at `uv run uvicorn app.main:app --host 0.0.0.0 --port <port>`.
- Sendblue's free tier uses a shared number — fine at this scale (a handful of verified senders); a dedicated line is $100/mo if you ever want guaranteed inbound-first delivery.

**Running on a first-gen Raspberry Pi Zero (ARMv6)?** Both `uv`'s managed Python builds and `cloudflared`'s official releases only target ARMv7+/ARM64 — neither works out of the box on genuine ARMv6 (the Pi Zero 2 W is ARMv7 and unaffected by any of this). If you're on the original Zero:
- **Python**: use the system-installed interpreter instead of letting `uv` try to download one (`requires-python = ">=3.11"` in `pyproject.toml` already reflects this — don't tighten it back to an exact 3.12 pin, since `uv python install` has no ARMv6 build to fetch).
- **`cloudflared`**: cross-compile it yourself — it's open-source Go, so `CGO_ENABLED=0 make cloudflared TARGET_OS=linux TARGET_ARCH=arm TARGET_ARM=6` from a released tag produces a working ARMv6 binary. Official releases crash with "illegal instruction."
- **`pydantic-core`** (a `fastapi`/`pydantic` dependency): it's a Rust extension with no ARMv6 wheel on PyPI, so a plain `uv sync` will try to compile it from source — extremely slow and memory-risky on 512MB, single-core hardware. [piwheels.org](https://www.piwheels.org) hosts prebuilt ARMv6 wheels for it, but getting `uv` to consistently prefer piwheels for just this one package without disturbing the rest of the (PyPI-based, macOS-compatible) lockfile proved fragile in practice — `--default-index` swaps the index globally for every package, and `[tool.uv.sources]` package-pinning to an `explicit` index didn't take effect as documented. The workaround that actually worked: run `uv lock --default-index https://www.piwheels.org/simple` directly on the Pi (regenerating a Pi-local lock, not committed back to the repo) whenever a fresh `.venv` build is needed there, then `uv sync`. Treat this as a standing manual step for this specific hardware, not something baked into the shared `pyproject.toml`/`uv.lock`.
- Drop the `uvicorn[standard]` extras (`uvloop`, `httptools`, `watchfiles`, `websockets`) — none of them matter at this traffic volume, and `uvloop`/`httptools` are C extensions with the same no-ARMv6-wheel problem. Plain `uvicorn` is pure Python.

## Tests

```bash
uv run pytest
```

Currently covers coordinate parsing (`tests/test_parsing.py`). The webhook flow (OTP verification, weather requests, unregistered-number handling, bad-signature rejection) has been exercised manually against a live NWS/Open-Meteo backend with Sendblue's send call mocked — see the plan doc for the full scenario list if you want to turn that into an automated suite.
