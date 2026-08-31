import argparse
import sys

from app import db, otp, sendblue
from app.config import config


def cmd_init_db(args: argparse.Namespace) -> None:
    db.init_db()
    print(f"Initialized database at {db.config.db_path}")


def cmd_add_number(args: argparse.Namespace) -> None:
    with db.get_connection() as conn:
        existing = db.get_phone_number(conn, args.phone_number)
        if existing is not None:
            print(f"{args.phone_number} already registered (id={existing['id']}).")
        else:
            db.add_phone_number(conn, args.phone_number, args.label)
            print(f"Added {args.phone_number}.")

    try:
        sendblue.create_contact(args.phone_number)
    except sendblue.SendblueError as e:
        print(f"(create_contact: {e} — continuing, likely already exists)")

    print(
        f"\nSendblue won't let us message {args.phone_number} until Sendblue itself\n"
        "considers them opted in — and that opt-in is inbound-first: THEY have to\n"
        f"text {config.sendblue_from_number} first (any message), not the other way\n"
        "around. Once Sendblue's dashboard shows them verified, run:\n"
        f"  uv run python cli.py verify-number {args.phone_number}"
    )


def cmd_verify_number(args: argparse.Namespace) -> None:
    with db.get_connection() as conn:
        row = db.get_phone_number(conn, args.phone_number)
        if row is None:
            print(f"No such number: {args.phone_number}", file=sys.stderr)
            sys.exit(1)

        code, code_hash, expires_at = otp.generate_code()
        otp_id = db.create_otp(conn, row["id"], code_hash, expires_at)
        reply = f"Your Weather-Messenger verification code is {code}"

        try:
            sendblue.send_message(row["phone_number"], reply)
        except sendblue.SendblueError as e:
            if "must be verified" in str(e).lower():
                print(
                    f"Sendblue rejected the send: {e}\n"
                    f"Run 'add-number {row['phone_number']}' first (or wait for them to "
                    "answer Sendblue's opt-in text), then retry this command.",
                    file=sys.stderr,
                )
                sys.exit(1)
            raise

        db.log_message(conn, row["id"], "outbound", "otp", reply)
        print(f"Sent OTP to {row['phone_number']} (expires {expires_at}).")

        attempts_left = 3
        try:
            while attempts_left > 0:
                entered = input("Enter the code you received: ")
                if otp.matches(entered, code_hash):
                    db.mark_otp_used(conn, otp_id)
                    db.set_verified_flag(conn, row["id"], True)
                    print(f"{row['phone_number']} verified.")
                    return
                attempts_left -= 1
                print(f"Incorrect code, try again ({attempts_left} attempts left).")
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.", file=sys.stderr)
            sys.exit(1)

        print(
            "Out of attempts. Run this command again for a fresh code.",
            file=sys.stderr,
        )
        sys.exit(1)


def cmd_list_numbers(args: argparse.Namespace) -> None:
    with db.get_connection() as conn:
        rows = db.list_phone_numbers(conn)
        if not rows:
            print("No numbers registered.")
            return
        for row in rows:
            status = "verified" if row["verified"] else "unverified"
            label = f" [{row['label']}]" if row["label"] else ""
            print(f"{row['id']:>3}  {row['phone_number']}{label}  {status}  {row['created_at']}")


def cmd_revoke(args: argparse.Namespace) -> None:
    with db.get_connection() as conn:
        row = db.get_phone_number(conn, args.phone_number)
        if row is None:
            print(f"No such number: {args.phone_number}", file=sys.stderr)
            sys.exit(1)
        db.set_verified_flag(conn, row["id"], False)
        print(f"Revoked {args.phone_number}.")


def main() -> None:
    parser = argparse.ArgumentParser(prog="weather-messenger")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init-db", help="Create the SQLite database from schema.sql")
    init_parser.set_defaults(func=cmd_init_db)

    add_parser = subparsers.add_parser(
        "add-number", help="Register a new phone number and trigger Sendblue's opt-in verification"
    )
    add_parser.add_argument("phone_number", help="E.164 format, e.g. +15551234567")
    add_parser.add_argument("--label", help="Optional friendly label, e.g. 'me'")
    add_parser.set_defaults(func=cmd_add_number)

    verify_parser = subparsers.add_parser(
        "verify-number", help="Send this app's OTP and verify it by typing the code back into the CLI"
    )
    verify_parser.add_argument("phone_number")
    verify_parser.set_defaults(func=cmd_verify_number)

    list_parser = subparsers.add_parser("list-numbers", help="List registered numbers")
    list_parser.set_defaults(func=cmd_list_numbers)

    revoke_parser = subparsers.add_parser("revoke", help="Revoke a number's verified status")
    revoke_parser.add_argument("phone_number")
    revoke_parser.set_defaults(func=cmd_revoke)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
