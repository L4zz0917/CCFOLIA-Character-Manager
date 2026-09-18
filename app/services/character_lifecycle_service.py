from __future__ import annotations

import shutil
from pathlib import Path

from app.db.database import get_connection
from app.ids import generate_app_id, generate_unique_cocofolia_id
from app.paths import IMAGES_DIR, PROJECT_ROOT


def list_deleted_characters():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                id,
                name,
                player_name,
                deleted_at
            FROM characters
            WHERE deleted_at IS NOT NULL
            ORDER BY
                deleted_at DESC,
                name COLLATE NOCASE ASC
            """
        ).fetchall()


def soft_delete_character(character_id: str) -> None:
    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE characters
            SET
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND deleted_at IS NULL
            """,
            (character_id,),
        )

        if result.rowcount == 0:
            raise ValueError(
                "キャラクターが見つからないか、既にゴミ箱にあります。"
            )


def restore_character(character_id: str) -> None:
    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE characters
            SET
                deleted_at = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
              AND deleted_at IS NOT NULL
            """,
            (character_id,),
        )

        if result.rowcount == 0:
            raise ValueError(
                "復元対象のキャラクターが見つかりません。"
            )


def permanently_delete_character(character_id: str) -> None:
    image_dir = IMAGES_DIR / character_id

    with get_connection() as conn:
        exists = conn.execute(
            """
            SELECT 1
            FROM characters
            WHERE id = ?
              AND deleted_at IS NOT NULL
            """,
            (character_id,),
        ).fetchone()

        if exists is None:
            raise ValueError(
                "完全削除できるのはゴミ箱内のキャラクターだけです。"
            )

        conn.execute(
            """
            DELETE FROM characters
            WHERE id = ?
            """,
            (character_id,),
        )

    if image_dir.exists():
        shutil.rmtree(
            image_dir,
            ignore_errors=True,
        )


def _copy_character_images(
    conn,
    source_character_id: str,
    new_character_id: str,
) -> None:
    rows = conn.execute(
        """
        SELECT
            relative_path,
            label,
            sort_order
        FROM character_images
        WHERE character_id = ?
        ORDER BY
            sort_order ASC,
            id ASC
        """,
        (source_character_id,),
    ).fetchall()

    target_dir = IMAGES_DIR / new_character_id
    target_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for row in rows:
        source_path = (
            PROJECT_ROOT
            / row["relative_path"]
        )

        if not source_path.is_file():
            continue

        image_id = generate_app_id()
        suffix = source_path.suffix.lower() or ".png"
        target_path = (
            target_dir
            / f"{image_id}{suffix}"
        )

        shutil.copy2(
            source_path,
            target_path,
        )

        relative = (
            target_path
            .relative_to(PROJECT_ROOT)
            .as_posix()
        )

        conn.execute(
            """
            INSERT INTO character_images(
                id,
                character_id,
                relative_path,
                label,
                sort_order
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                image_id,
                new_character_id,
                relative,
                row["label"],
                row["sort_order"],
            ),
        )


def _copy_rows_with_new_ids(
    conn,
    table_name: str,
    columns: list[str],
    source_character_id: str,
    new_character_id: str,
) -> None:
    select_columns = ", ".join(columns)

    rows = conn.execute(
        f"""
        SELECT {select_columns}
        FROM {table_name}
        WHERE character_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (source_character_id,),
    ).fetchall()

    insert_columns = ", ".join(
        [
            "id",
            "character_id",
            *columns,
        ]
    )

    placeholders = ", ".join(
        "?"
        for _ in range(
            2 + len(columns)
        )
    )

    for row in rows:
        values = [
            generate_app_id(),
            new_character_id,
            *[
                row[column]
                for column in columns
            ],
        ]

        conn.execute(
            f"""
            INSERT INTO {table_name}(
                {insert_columns}
            )
            VALUES ({placeholders})
            """,
            values,
        )


def duplicate_character(
    source_character_id: str,
) -> str:
    with get_connection() as conn:
        source = conn.execute(
            """
            SELECT *
            FROM characters
            WHERE id = ?
              AND deleted_at IS NULL
            """,
            (source_character_id,),
        ).fetchone()

        if source is None:
            raise ValueError(
                "複製元のキャラクターが見つかりません。"
            )

        new_character_id = generate_app_id()
        new_export_id = generate_unique_cocofolia_id(
            conn
        )

        new_name = (
            f"{source['name']} のコピー"
        )

        conn.execute(
            """
            INSERT INTO characters(
                id,
                name,
                player_name,
                memo,
                initiative,
                external_url,
                color,
                secret,
                invisible,
                hide_status,
                cocofolia_source_id,
                cocofolia_export_id,
                created_at,
                updated_at,
                deleted_at
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                '', ?,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                NULL
            )
            """,
            (
                new_character_id,
                new_name,
                source["player_name"],
                source["memo"],
                source["initiative"],
                source["external_url"],
                source["color"],
                source["secret"],
                source["invisible"],
                source["hide_status"],
                new_export_id,
            ),
        )

        _copy_character_images(
            conn,
            source_character_id,
            new_character_id,
        )

        _copy_rows_with_new_ids(
            conn,
            "statuses",
            [
                "label",
                "current_value",
                "max_value",
                "sort_order",
            ],
            source_character_id,
            new_character_id,
        )

        _copy_rows_with_new_ids(
            conn,
            "params",
            [
                "label",
                "value",
                "sort_order",
            ],
            source_character_id,
            new_character_id,
        )

        _copy_rows_with_new_ids(
            conn,
            "derived_values",
            [
                "label",
                "formula",
                "last_value",
                "error",
                "sort_order",
            ],
            source_character_id,
            new_character_id,
        )

        _copy_rows_with_new_ids(
            conn,
            "skills",
            [
                "label",
                "value",
                "category",
                "sort_order",
            ],
            source_character_id,
            new_character_id,
        )

        _copy_rows_with_new_ids(
            conn,
            "memos",
            [
                "title",
                "body",
                "is_private",
                "sort_order",
            ],
            source_character_id,
            new_character_id,
        )

        _copy_rows_with_new_ids(
            conn,
            "chat_palettes",
            [
                "name",
                "mode",
                "content",
                "sort_order",
            ],
            source_character_id,
            new_character_id,
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO character_tags(
                character_id,
                tag_id
            )
            SELECT
                ?,
                tag_id
            FROM character_tags
            WHERE character_id = ?
            """,
            (
                new_character_id,
                source_character_id,
            ),
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO character_groups(
                character_id,
                group_id
            )
            SELECT
                ?,
                group_id
            FROM character_groups
            WHERE character_id = ?
            """,
            (
                new_character_id,
                source_character_id,
            ),
        )

    return new_character_id

# ---------------------------------------------------------------------------
# Phase 27.1: bulk soft delete
# ---------------------------------------------------------------------------

def soft_delete_characters(
    character_ids: list[str],
) -> int:
    ids = []

    for raw_id in character_ids:
        value = str(
            raw_id
        ).strip()

        if value and value not in ids:
            ids.append(value)

    if not ids:
        return 0

    placeholders = ", ".join(
        "?"
        for _ in ids
    )

    with get_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id
            FROM characters
            WHERE id IN ({placeholders})
              AND deleted_at IS NULL
            """,
            ids,
        ).fetchall()

        found_ids = {
            row["id"]
            for row in rows
        }

        if found_ids != set(ids):
            raise ValueError(
                "削除対象の一部が見つからないか、既にゴミ箱にあります。"
            )

        result = conn.execute(
            f"""
            UPDATE characters
            SET
                deleted_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id IN ({placeholders})
              AND deleted_at IS NULL
            """,
            ids,
        )

    return int(
        result.rowcount
        if result.rowcount is not None
        else len(ids)
    )

# ---------------------------------------------------------------------------
# Phase 35: permanently delete all trashed characters
# ---------------------------------------------------------------------------

def permanently_delete_all_deleted_characters() -> int:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM characters
            WHERE deleted_at IS NOT NULL
            """
        ).fetchall()

        character_ids = [
            row["id"]
            for row in rows
        ]

        if not character_ids:
            return 0

        conn.execute(
            """
            DELETE FROM characters
            WHERE deleted_at IS NOT NULL
            """
        )

    for character_id in character_ids:
        image_dir = (
            IMAGES_DIR
            / character_id
        )

        if image_dir.exists():
            shutil.rmtree(
                image_dir,
                ignore_errors=True,
            )

    return len(character_ids)
