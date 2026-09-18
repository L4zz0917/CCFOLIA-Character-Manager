from __future__ import annotations

from app.db.database import get_connection


COLUMN = "quick_memo"


def ensure_quick_memo_schema():
    with get_connection() as conn:
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(characters)"
            ).fetchall()
        }

        if COLUMN not in columns:
            conn.execute(
                '''
                ALTER TABLE characters
                ADD COLUMN quick_memo TEXT NOT NULL DEFAULT ''
                '''
            )


def get_quick_memo(character_id: str) -> str:
    ensure_quick_memo_schema()

    with get_connection() as conn:
        row = conn.execute(
            '''
            SELECT quick_memo
            FROM characters
            WHERE id = ?
              AND deleted_at IS NULL
            ''',
            (character_id,),
        ).fetchone()

    if row is None:
        return ""

    return str(row["quick_memo"] or "")


def set_quick_memo(
    character_id: str,
    text: str,
):
    ensure_quick_memo_schema()

    value = str(text or "")

    if len(value) > 200_000:
        raise ValueError(
            "Quick Memo が長すぎます。"
        )

    with get_connection() as conn:
        conn.execute(
            '''
            UPDATE characters
            SET quick_memo = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND deleted_at IS NULL
            ''',
            (
                value,
                character_id,
            ),
        )
