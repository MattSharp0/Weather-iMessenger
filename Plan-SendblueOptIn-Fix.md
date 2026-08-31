**Status: done (2026-08-30).** `request_contact_verification` removed from
`app/sendblue.py`/`cli.py` (it never did what its docstring claimed — see
below); docstrings, `CLAUDE.md`, and `README.md` updated to describe the real
inbound-first flow. First/last name turned out to be a portal-only
requirement — `create_contact` succeeds fine via the API with empty names,
so no code change needed there.

# Fix: Sendblue opt-in flow is documented/coded backwards

## Problem

Every reference to Sendblue's own opt-in step in this codebase describes it as
**outbound-first**: we call `request_contact_verification`, Sendblue texts the
recipient, they reply, and only then can we message them.

The actual flow (at least on the free/shared tier) is **inbound-first**: the
recipient has to text *our* Sendblue number themselves before Sendblue
considers them opted in. Nothing we call via the API triggers an outbound
opt-in text to them.

## How this was found (2026-08-30, adding Haley's number)

- `cli.py add-number +17134099853 --label haley` → `create_contact` succeeded
  (confirmed via `GET /api/v2/contacts/{number}`, contact existed, not opted
  out), but `request_contact_verification` (`POST /api/v2/contacts/verify`)
  consistently failed with `"No contact found for this number"`.
- Ruled out: field-name mismatch (`"number"` is correct — `"phone"` gives
  `"Missing fields"`), propagation delay (failed immediately after a fresh
  confirmed create), account-wide outage (the identical verify call succeeds
  immediately for the admin's own already-opted-in number).
- Root cause surfaced via the Sendblue web portal: adding a contact there
  prompts for first/last name (≥2 chars each), then shows *"Next step: You'll
  need to send a text message from this phone number to verify ownership."*
  I.e. verification is recipient-initiated (they text us), not
  Sendblue-initiated (Sendblue texts them). Once Haley texted the shared
  Sendblue number, the portal marked her verified and `cli.py verify-number`
  worked normally.
- Likely why `/v2/contacts/verify` returns "no contact found": it's probably
  gated on the same underlying state the portal's inbound-text step sets, not
  a standalone "send opt-in text" trigger — so it fails until they've already
  texted in, at which point it's presumably a no-op (matches: it returned
  `{"status": "OK"}` immediately for the admin's already-verified number).

## Scope — places with the wrong (outbound-first) model

- [app/sendblue.py:41](app/sendblue.py:41) — `request_contact_verification`
  docstring.
- [cli.py:36](cli.py:36) — the message `add-number` prints after triggering
  verification ("Sendblue sent its own opt-in verification text... that must
  be answered first").
- [cli.py:20-27](cli.py:20) — behavior itself: currently calls
  `create_contact` then `request_contact_verification` and treats a
  verification failure as fatal (`sys.exit(1)`) with a "couldn't be validated
  as a real mobile line" message — misleading, since failure here is the
  *expected* state for a brand-new number until they text in, not a sign of
  an invalid number.
- [CLAUDE.md](CLAUDE.md) — "Two-layer, both-admin-driven verification"
  section describes layer 1 as Sendblue-initiated.
- [README.md](README.md) — step 4 of setup ("Register yourself...") and the
  "Notes from getting this actually working" section both describe
  replying to a Sendblue-sent text.

## Proposed changes

1. **`add-number`**: keep `create_contact`, but stop treating
   `request_contact_verification` failure as fatal/exceptional — it will
   normally fail for a brand-new number. Either drop the call entirely (it
   may serve no purpose in this account tier) or keep it as a best-effort,
   non-fatal probe, and change the printed guidance to tell the admin: *have
   the recipient text `SENDBLUE_FROM_NUMBER` first, then re-run
   `verify-number`.*
2. Consider passing `first_name`/`last_name` on `create_contact` (portal
   requires ≥2 chars each for its manual flow) — confirm via API whether this
   is actually required outside the portal, or whether empty names are fine
   for the API path (earlier testing showed `create_contact` succeeding with
   empty names, so this may be portal-only).
3. Update docstrings/comments in `app/sendblue.py` to describe the real
   (inbound-first) mechanics, matching the existing style of documenting
   Sendblue quirks "found the hard way."
4. Update `CLAUDE.md`'s two-layer verification section and `README.md`'s
   setup walkthrough + "notes from getting this working" section to match.

## Open questions

- Does `request_contact_verification` do anything useful at all, or can it
  be removed outright in favor of just `create_contact` + instructing the
  admin to have the recipient text in?
- Is the ≥2-char first/last name requirement enforced by the API itself for
  any part of this flow, or purely a portal UI constraint?
