import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import config

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


@contextmanager
def get_connection():
    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text())


def get_phone_number(conn: sqlite3.Connection, phone_number: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM phone_numbers WHERE phone_number = ?", (phone_number,)
    ).fetchone()


def add_phone_number(conn: sqlite3.Connection, phone_number: str, label: str | None) -> int:
    cur = conn.execute(
        "INSERT INTO phone_numbers (phone_number, label) VALUES (?, ?)",
        (phone_number, label),
    )
    return cur.lastrowid


def set_verified_flag(conn: sqlite3.Connection, phone_number_id: int, verified: bool) -> None:
    conn.execute(
        "UPDATE phone_numbers SET verified = ? WHERE id = ?",
        (1 if verified else 0, phone_number_id),
    )


def list_phone_numbers(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM phone_numbers ORDER BY created_at"
    ).fetchall()


def create_otp(conn: sqlite3.Connection, phone_number_id: int, code_hash: str, expires_at: str) -> int:
    cur = conn.execute(
        "INSERT INTO otp_codes (phone_number_id, code_hash, expires_at) VALUES (?, ?, ?)",
        (phone_number_id, code_hash, expires_at),
    )
    return cur.lastrowid


def mark_otp_used(conn: sqlite3.Connection, otp_id: int) -> None:
    conn.execute(
        "UPDATE otp_codes SET used_at = CURRENT_TIMESTAMP WHERE id = ?", (otp_id,)
    )


def log_message(
    conn: sqlite3.Connection,
    phone_number_id: int,
    direction: str,
    message_type: str,
    contents: str | None,
    parsed_lat: float | None = None,
    parsed_lon: float | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO messages (phone_number_id, direction, message_type, contents, parsed_lat, parsed_lon)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (phone_number_id, direction, message_type, contents, parsed_lat, parsed_lon),
    )
