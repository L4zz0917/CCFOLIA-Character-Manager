from __future__ import annotations

import math
import shutil
from pathlib import Path

from app.db.database import get_connection
from app.ids import generate_app_id, generate_unique_cocofolia_id
from app.paths import IMAGES_DIR, PROJECT_ROOT


def create_character(name: str) -> str:
    name = name.strip()
    if not name:
        raise ValueError("キャラクター名を入力してください。")

    with get_connection() as conn:
        character_id = generate_app_id()
        export_id = generate_unique_cocofolia_id(conn)
        conn.execute(
            """
            INSERT INTO characters(
                id,
                name,
                cocofolia_export_id
            )
            VALUES (?, ?, ?)
            """,
            (character_id, name, export_id),
        )
    return character_id


def get_character(character_id: str):
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM characters
            WHERE id = ?
              AND deleted_at IS NULL
            """,
            (character_id,),
        ).fetchone()


def get_character_bundle(character_id: str) -> dict:
    with get_connection() as conn:
        character = conn.execute(
            """
            SELECT *
            FROM characters
            WHERE id = ?
              AND deleted_at IS NULL
            """,
            (character_id,),
        ).fetchone()

        if character is None:
            raise ValueError("キャラクターが見つかりません。")

        images = conn.execute(
            """
            SELECT *
            FROM character_images
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        statuses = conn.execute(
            """
            SELECT *
            FROM statuses
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        params = conn.execute(
            """
            SELECT *
            FROM params
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        memos = conn.execute(
            """
            SELECT *
            FROM memos
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        tags = conn.execute(
            """
            SELECT t.id, t.name
            FROM tags t
            JOIN character_tags ct
              ON ct.tag_id = t.id
            WHERE ct.character_id = ?
            ORDER BY t.name COLLATE NOCASE ASC
            """,
            (character_id,),
        ).fetchall()

        group_ids = [
            row["group_id"]
            for row in conn.execute(
                """
                SELECT group_id
                FROM character_groups
                WHERE character_id = ?
                """,
                (character_id,),
            ).fetchall()
        ]

    return {
        "character": dict(character),
        "images": [dict(row) for row in images],
        "statuses": [dict(row) for row in statuses],
        "params": [dict(row) for row in params],
        "memos": [dict(row) for row in memos],
        "tags": [dict(row) for row in tags],
        "group_ids": group_ids,
    }


def _parse_tag_search(search_text: str) -> list[str]:
    normalized = search_text.replace("、", ",")
    parts = [part.strip() for part in normalized.split(",")]
    return [part for part in parts if part]


def list_characters(
    search_text: str = "",
    search_mode: str = "keyword",
    group_id: str | None = None,
):
    search_text = search_text.strip()
    conditions = ["c.deleted_at IS NULL"]
    params = []

    if search_text:
        if search_mode == "tag":
            tag_terms = _parse_tag_search(search_text)
            for term in tag_terms:
                conditions.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM character_tags ct
                        JOIN tags t ON t.id = ct.tag_id
                        WHERE ct.character_id = c.id
                          AND t.name LIKE ?
                    )
                    """
                )
                params.append(f"%{term}%")
        else:
            conditions.append(
                """
                (
                    c.name LIKE ?
                    OR c.memo LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM memos m
                        WHERE m.character_id = c.id
                          AND (
                              m.title LIKE ?
                              OR m.body LIKE ?
                          )
                    )
                )
                """
            )
            needle = f"%{search_text}%"
            params.extend([needle, needle, needle, needle])

    where_sql = " AND ".join(conditions)

    if group_id is None:
        sql = f"""
            SELECT
                c.*,
                (
                    SELECT ci.relative_path
                    FROM character_images ci
                    WHERE ci.character_id = c.id
                    ORDER BY ci.sort_order ASC, ci.id ASC
                    LIMIT 1
                ) AS main_image
            FROM characters c
            WHERE {where_sql}
            ORDER BY c.name COLLATE NOCASE ASC, c.id ASC
        """
        query_params = params
    else:
        sql = f"""
            WITH RECURSIVE descendants(id) AS (
                SELECT ?
                UNION ALL
                SELECT g.id
                FROM groups g
                JOIN descendants d
                  ON g.parent_group_id = d.id
            )
            SELECT
                c.*,
                (
                    SELECT ci.relative_path
                    FROM character_images ci
                    WHERE ci.character_id = c.id
                    ORDER BY ci.sort_order ASC, ci.id ASC
                    LIMIT 1
                ) AS main_image
            FROM characters c
            WHERE {where_sql}
              AND EXISTS (
                    SELECT 1
                    FROM character_groups cg
                    JOIN descendants d
                      ON d.id = cg.group_id
                    WHERE cg.character_id = c.id
              )
            ORDER BY c.name COLLATE NOCASE ASC, c.id ASC
        """
        query_params = [group_id, *params]

    with get_connection() as conn:
        return conn.execute(sql, query_params).fetchall()


def list_groups():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, name, parent_group_id, sort_order
            FROM groups
            ORDER BY sort_order ASC, name COLLATE NOCASE ASC
            """
        ).fetchall()


def create_group(name: str, parent_group_id: str | None = None) -> str:
    name = name.strip()
    if not name:
        raise ValueError("グループ名を入力してください。")

    group_id = generate_app_id()

    with get_connection() as conn:
        if parent_group_id is not None:
            parent = conn.execute(
                "SELECT 1 FROM groups WHERE id = ?",
                (parent_group_id,),
            ).fetchone()
            if parent is None:
                raise ValueError("親グループが見つかりません。")

        max_order = conn.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) + 1 AS next_order
            FROM groups
            WHERE parent_group_id IS ?
            """,
            (parent_group_id,),
        ).fetchone()["next_order"]

        conn.execute(
            """
            INSERT INTO groups(
                id,
                name,
                parent_group_id,
                sort_order
            )
            VALUES (?, ?, ?, ?)
            """,
            (group_id, name, parent_group_id, max_order),
        )

    return group_id


def rename_group(group_id: str, new_name: str) -> None:
    new_name = new_name.strip()
    if not new_name:
        raise ValueError("グループ名を入力してください。")

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE groups
            SET name = ?
            WHERE id = ?
            """,
            (new_name, group_id),
        )
        if result.rowcount == 0:
            raise ValueError("グループが見つかりません。")


def delete_group(group_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM groups WHERE id = ?",
            (group_id,),
        )


def list_tags():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, name
            FROM tags
            ORDER BY name COLLATE NOCASE ASC
            """
        ).fetchall()


def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()
    return default if row is None else str(row["value"])


def get_bool_setting(key: str, default: bool = False) -> bool:
    fallback = "1" if default else "0"
    return get_setting(key, fallback) == "1"


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )


def copy_image_for_character(character_id: str, source_path: str) -> dict:
    source = Path(source_path)
    if not source.is_file():
        raise ValueError("画像ファイルが見つかりません。")

    suffix = source.suffix.lower() or ".png"
    target_dir = IMAGES_DIR / character_id
    target_dir.mkdir(parents=True, exist_ok=True)

    image_id = generate_app_id()
    target = target_dir / f"{image_id}{suffix}"
    shutil.copy2(source, target)

    relative = target.relative_to(PROJECT_ROOT).as_posix()

    return {
        "id": image_id,
        "character_id": character_id,
        "relative_path": relative,
        "label": "",
        "sort_order": 0,
    }


def _finite_number(value, field_name: str, allow_blank: bool = False):
    if value is None:
        if allow_blank:
            return None
        raise ValueError(f"{field_name}を入力してください。")

    if isinstance(value, str):
        value = value.strip()
        if value == "":
            if allow_blank:
                return None
            raise ValueError(f"{field_name}を入力してください。")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name}は数値で入力してください。") from exc

    if not math.isfinite(number):
        raise ValueError(f"{field_name}は有限の数値で入力してください。")

    return number


def _clean_tag_names(tag_names: list[str]) -> list[str]:
    output = []
    seen = set()

    for raw in tag_names:
        name = str(raw).strip()
        if not name:
            continue

        key = name.casefold()
        if key in seen:
            continue

        seen.add(key)
        output.append(name)

    return output


def save_character_bundle(
    character_id: str,
    character_data: dict,
    images: list[dict],
    statuses: list[dict],
    params: list[dict],
    memos: list[dict],
    tag_names: list[str] | None = None,
    group_ids: list[str] | None = None,
) -> None:
    name = str(character_data.get("name", "")).strip()
    if not name:
        raise ValueError("キャラクター名は空にできません。")

    initiative = _finite_number(
        character_data.get("initiative", "0"),
        "イニシアティブ",
    )

    clean_statuses = []
    for index, row in enumerate(statuses):
        label = str(row.get("label", "")).strip()
        current_text = str(row.get("current", "")).strip()
        max_text = str(row.get("max", "")).strip()

        if not label and not current_text and not max_text:
            continue
        if not label:
            raise ValueError(f"ステータス {index + 1} の名前が空です。")

        current = _finite_number(
            current_text,
            f"ステータス「{label}」の現在値",
            allow_blank=True,
        )
        maximum = _finite_number(
            max_text,
            f"ステータス「{label}」の最大値",
            allow_blank=True,
        )

        clean_statuses.append(
            {
                "label": label,
                "current": current,
                "max": maximum,
            }
        )

    clean_params = []
    for row in params:
        label = str(row.get("label", "")).strip()
        value = str(row.get("value", ""))

        if not label and not value.strip():
            continue
        if not label:
            raise ValueError("パラメータ名が空の行があります。")

        clean_params.append({"label": label, "value": value})

    clean_memos = []
    for row in memos:
        title = str(row.get("title", "")).strip()
        body = str(row.get("body", ""))
        private = bool(row.get("private", False))

        if not title and not body.strip():
            continue

        clean_memos.append(
            {
                "title": title or "メモ",
                "body": body,
                "private": private,
            }
        )

    clean_tags = _clean_tag_names(tag_names or [])
    clean_group_ids = list(dict.fromkeys(group_ids or []))

    with get_connection() as conn:
        exists = conn.execute(
            """
            SELECT 1
            FROM characters
            WHERE id = ?
              AND deleted_at IS NULL
            """,
            (character_id,),
        ).fetchone()

        if exists is None:
            raise ValueError("保存対象のキャラクターが見つかりません。")

        conn.execute(
            """
            UPDATE characters
            SET
                name = ?,
                player_name = ?,
                initiative = ?,
                external_url = ?,
                color = ?,
                secret = ?,
                invisible = ?,
                hide_status = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                name,
                str(character_data.get("player_name", "")),
                initiative,
                str(character_data.get("external_url", "")),
                str(character_data.get("color", "#888888")),
                1 if character_data.get("secret") else 0,
                1 if character_data.get("invisible") else 0,
                1 if character_data.get("hide_status") else 0,
                character_id,
            ),
        )

        conn.execute(
            "DELETE FROM character_images WHERE character_id = ?",
            (character_id,),
        )
        for index, image in enumerate(images):
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
                    str(image.get("id") or generate_app_id()),
                    character_id,
                    str(image["relative_path"]),
                    str(image.get("label", "")),
                    index,
                ),
            )

        conn.execute(
            "DELETE FROM statuses WHERE character_id = ?",
            (character_id,),
        )
        for index, row in enumerate(clean_statuses):
            conn.execute(
                """
                INSERT INTO statuses(
                    id,
                    character_id,
                    label,
                    current_value,
                    max_value,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_app_id(),
                    character_id,
                    row["label"],
                    row["current"],
                    row["max"],
                    index,
                ),
            )

        conn.execute(
            "DELETE FROM params WHERE character_id = ?",
            (character_id,),
        )
        for index, row in enumerate(clean_params):
            conn.execute(
                """
                INSERT INTO params(
                    id,
                    character_id,
                    label,
                    value,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    generate_app_id(),
                    character_id,
                    row["label"],
                    row["value"],
                    index,
                ),
            )

        conn.execute(
            "DELETE FROM memos WHERE character_id = ?",
            (character_id,),
        )
        for index, row in enumerate(clean_memos):
            conn.execute(
                """
                INSERT INTO memos(
                    id,
                    character_id,
                    title,
                    body,
                    is_private,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_app_id(),
                    character_id,
                    row["title"],
                    row["body"],
                    1 if row["private"] else 0,
                    index,
                ),
            )

        conn.execute(
            "DELETE FROM character_tags WHERE character_id = ?",
            (character_id,),
        )
        for tag_name in clean_tags:
            row = conn.execute(
                """
                SELECT id
                FROM tags
                WHERE name = ? COLLATE NOCASE
                """,
                (tag_name,),
            ).fetchone()

            if row is None:
                tag_id = generate_app_id()
                conn.execute(
                    """
                    INSERT INTO tags(id, name)
                    VALUES (?, ?)
                    """,
                    (tag_id, tag_name),
                )
            else:
                tag_id = row["id"]

            conn.execute(
                """
                INSERT OR IGNORE INTO character_tags(
                    character_id,
                    tag_id
                )
                VALUES (?, ?)
                """,
                (character_id, tag_id),
            )

        conn.execute(
            "DELETE FROM character_groups WHERE character_id = ?",
            (character_id,),
        )
        for group_id in clean_group_ids:
            exists = conn.execute(
                "SELECT 1 FROM groups WHERE id = ?",
                (group_id,),
            ).fetchone()
            if exists is None:
                continue

            conn.execute(
                """
                INSERT OR IGNORE INTO character_groups(
                    character_id,
                    group_id
                )
                VALUES (?, ?)
                """,
                (character_id, group_id),
            )

# ---------------------------------------------------------------------------
# Phase 25: bulk classification helpers
# ---------------------------------------------------------------------------

def add_tags_to_characters(
    character_ids,
    tag_names,
):
    ids = [
        str(value).strip()
        for value in character_ids
        if str(value).strip()
    ]
    names = _clean_tag_names(
        list(tag_names or [])
    )

    if not ids or not names:
        return 0

    added = 0

    with get_connection() as conn:
        tag_ids = []

        for tag_name in names:
            row = conn.execute(
                """
                SELECT id
                FROM tags
                WHERE name = ? COLLATE NOCASE
                """,
                (tag_name,),
            ).fetchone()

            if row is None:
                tag_id = generate_app_id()
                conn.execute(
                    """
                    INSERT INTO tags(id, name)
                    VALUES (?, ?)
                    """,
                    (tag_id, tag_name),
                )
            else:
                tag_id = row["id"]

            tag_ids.append(tag_id)

        for character_id in ids:
            exists = conn.execute(
                """
                SELECT 1
                FROM characters
                WHERE id = ?
                  AND deleted_at IS NULL
                """,
                (character_id,),
            ).fetchone()

            if exists is None:
                continue

            for tag_id in tag_ids:
                result = conn.execute(
                    """
                    INSERT OR IGNORE INTO character_tags(
                        character_id,
                        tag_id
                    )
                    VALUES (?, ?)
                    """,
                    (
                        character_id,
                        tag_id,
                    ),
                )

                if result.rowcount:
                    added += 1

    return added


def add_group_to_characters(
    character_ids,
    group_id,
):
    ids = [
        str(value).strip()
        for value in character_ids
        if str(value).strip()
    ]
    group_id = str(
        group_id or ""
    ).strip()

    if not ids or not group_id:
        return 0

    added = 0

    with get_connection() as conn:
        group_exists = conn.execute(
            """
            SELECT 1
            FROM groups
            WHERE id = ?
            """,
            (group_id,),
        ).fetchone()

        if group_exists is None:
            raise ValueError(
                "グループが見つかりません。"
            )

        for character_id in ids:
            exists = conn.execute(
                """
                SELECT 1
                FROM characters
                WHERE id = ?
                  AND deleted_at IS NULL
                """,
                (character_id,),
            ).fetchone()

            if exists is None:
                continue

            result = conn.execute(
                """
                INSERT OR IGNORE INTO character_groups(
                    character_id,
                    group_id
                )
                VALUES (?, ?)
                """,
                (
                    character_id,
                    group_id,
                ),
            )

            if result.rowcount:
                added += 1

    return added

# ---------------------------------------------------------------------------
# Phase 25.1: ungrouped character listing
# ---------------------------------------------------------------------------

def list_ungrouped_characters(
    search_text: str = "",
    search_mode: str = "keyword",
):
    search_text = search_text.strip()
    conditions = [
        "c.deleted_at IS NULL",
        """
        NOT EXISTS (
            SELECT 1
            FROM character_groups cg
            WHERE cg.character_id = c.id
        )
        """,
    ]
    params = []

    if search_text:
        if search_mode == "tag":
            tag_terms = _parse_tag_search(search_text)
            for term in tag_terms:
                conditions.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM character_tags ct
                        JOIN tags t ON t.id = ct.tag_id
                        WHERE ct.character_id = c.id
                          AND t.name LIKE ?
                    )
                    """
                )
                params.append(f"%{term}%")
        else:
            conditions.append(
                """
                (
                    c.name LIKE ?
                    OR c.memo LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM memos m
                        WHERE m.character_id = c.id
                          AND (
                              m.title LIKE ?
                              OR m.body LIKE ?
                          )
                    )
                )
                """
            )
            needle = f"%{search_text}%"
            params.extend([needle, needle, needle, needle])

    where_sql = " AND ".join(conditions)

    sql = f"""
        SELECT
            c.*,
            (
                SELECT ci.relative_path
                FROM character_images ci
                WHERE ci.character_id = c.id
                ORDER BY ci.sort_order ASC, ci.id ASC
                LIMIT 1
            ) AS main_image
        FROM characters c
        WHERE {where_sql}
        ORDER BY c.name COLLATE NOCASE ASC, c.id ASC
    """

    with get_connection() as conn:
        return conn.execute(sql, params).fetchall()

# ---------------------------------------------------------------------------
# Phase 27.1: persist group tree after drag & drop
# ---------------------------------------------------------------------------

def persist_group_tree_structure(
    rows: list[tuple[str, str | None, int]],
) -> None:
    normalized = []

    for group_id, parent_group_id, sort_order in rows:
        group_id = str(group_id).strip()

        if not group_id:
            raise ValueError(
                "グループIDが空です。"
            )

        if parent_group_id is not None:
            parent_group_id = str(
                parent_group_id
            ).strip() or None

        normalized.append(
            (
                group_id,
                parent_group_id,
                int(sort_order),
            )
        )

    with get_connection() as conn:
        existing_rows = conn.execute(
            """
            SELECT id
            FROM groups
            """
        ).fetchall()

        existing_ids = {
            row["id"]
            for row in existing_rows
        }

        received_ids = {
            group_id
            for group_id, _, _
            in normalized
        }

        if (
            len(received_ids)
            != len(normalized)
        ):
            raise ValueError(
                "グループ構造に重複したIDがあります。"
            )

        if received_ids != existing_ids:
            raise ValueError(
                "グループ構造が現在のデータと一致しません。"
            )

        parent_map = {}

        for (
            group_id,
            parent_group_id,
            sort_order,
        ) in normalized:
            if (
                parent_group_id is not None
                and parent_group_id
                not in existing_ids
            ):
                raise ValueError(
                    "移動先グループが見つかりません。"
                )

            if parent_group_id == group_id:
                raise ValueError(
                    "グループ自身を親にはできません。"
                )

            if sort_order < 0:
                raise ValueError(
                    "並び順が不正です。"
                )

            parent_map[group_id] = (
                parent_group_id
            )

        # Defensive cycle validation.
        for group_id in existing_ids:
            seen = {
                group_id
            }
            current = parent_map.get(
                group_id
            )

            while current is not None:
                if current in seen:
                    raise ValueError(
                        "循環するグループ階層は作成できません。"
                    )

                seen.add(current)
                current = parent_map.get(
                    current
                )

        for (
            group_id,
            parent_group_id,
            sort_order,
        ) in normalized:
            conn.execute(
                """
                UPDATE groups
                SET
                    parent_group_id = ?,
                    sort_order = ?
                WHERE id = ?
                """,
                (
                    parent_group_id,
                    sort_order,
                    group_id,
                ),
            )

# PHASE37_TAGLESS_FILTER
_PHASE37_TAGLESS_SENTINEL = "__CCM_TAGLESS__"
_phase37_list_characters_base = list_characters

try:
    _phase37_list_ungrouped_base = list_ungrouped_characters
except NameError:
    _phase37_list_ungrouped_base = None


def _phase37_only_tagless(rows):
    rows = list(rows)

    if not rows:
        return rows

    ids = [
        str(row["id"])
        for row in rows
    ]

    placeholders = ",".join(
        "?"
        for _ in ids
    )

    with get_connection() as conn:
        tagged = {
            str(row["character_id"])
            for row in conn.execute(
                f'''
                SELECT DISTINCT character_id
                FROM character_tags
                WHERE character_id IN ({placeholders})
                ''',
                ids,
            ).fetchall()
        }

    return [
        row
        for row in rows
        if str(row["id"]) not in tagged
    ]


def list_characters(
    search_text: str = "",
    search_mode: str = "keyword",
    group_id: str | None = None,
):
    if (
        search_mode == "tag"
        and search_text.strip()
        == _PHASE37_TAGLESS_SENTINEL
    ):
        rows = _phase37_list_characters_base(
            search_text="",
            search_mode="keyword",
            group_id=group_id,
        )
        return _phase37_only_tagless(
            rows
        )

    return _phase37_list_characters_base(
        search_text=search_text,
        search_mode=search_mode,
        group_id=group_id,
    )


if _phase37_list_ungrouped_base is not None:
    def list_ungrouped_characters(
        search_text: str = "",
        search_mode: str = "keyword",
    ):
        if (
            search_mode == "tag"
            and search_text.strip()
            == _PHASE37_TAGLESS_SENTINEL
        ):
            rows = _phase37_list_ungrouped_base(
                search_text="",
                search_mode="keyword",
            )
            return _phase37_only_tagless(
                rows
            )

        return _phase37_list_ungrouped_base(
            search_text=search_text,
            search_mode=search_mode,
        )
