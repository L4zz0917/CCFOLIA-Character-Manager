import secrets
import string
import uuid

from sqlite3 import Connection


COCOFOLIA_ALPHABET = string.ascii_letters + string.digits


def generate_app_id() -> str:
    return uuid.uuid4().hex


def generate_cocofolia_id(length: int = 20) -> str:
    return "".join(secrets.choice(COCOFOLIA_ALPHABET) for _ in range(length))


def generate_unique_cocofolia_id(conn: Connection) -> str:
    while True:
        candidate = generate_cocofolia_id()

        row = conn.execute(
            """
            SELECT 1
            FROM characters
            WHERE cocofolia_export_id = ?
            LIMIT 1
            """,
            (candidate,),
        ).fetchone()

        if row is None:
            return candidate
