from __future__ import annotations

# IMAGES_MODULE_SERVICE_V1

import mimetypes
import shutil
from pathlib import Path

from app.db.database import get_connection
from app.ids import generate_app_id
from app.paths import IMAGE_ASSETS_DIR, PROJECT_ROOT


_IMAGE_CONTENT_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".jfif": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".avif": "image/avif",
}


def _clean_ids(values) -> list[str]:
    output = []
    seen = set()

    for value in values or []:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)

    return output


def _clean_tag_names(values) -> list[str]:
    output = []
    seen = set()

    for value in values or []:
        name = str(value).strip()
        if not name:
            continue

        key = name.casefold()
        if key in seen:
            continue

        seen.add(key)
        output.append(name)

    return output


def _parse_tag_search(search_text: str) -> list[str]:
    normalized = str(search_text or "").replace("、", ",")
    return [
        part.strip()
        for part in normalized.split(",")
        if part.strip()
    ]


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in _IMAGE_CONTENT_TYPES:
        return _IMAGE_CONTENT_TYPES[suffix]

    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or ""


def _require_image_file(source_path: str | Path) -> tuple[Path, str]:
    source = Path(source_path).expanduser().resolve()

    if not source.is_file():
        raise ValueError("画像ファイルが見つかりません。")

    content_type = _guess_content_type(source)
    if not content_type.startswith("image/"):
        raise ValueError("画像ファイルを選択してください。")

    return source, content_type


def import_image_asset(
    source_path: str | Path,
    display_name: str = "",
    source: str = "local",
) -> str:
    source_file, content_type = _require_image_file(source_path)

    asset_id = generate_app_id()
    target_dir = IMAGE_ASSETS_DIR / asset_id
    target_dir.mkdir(parents=True, exist_ok=True)

    suffix = source_file.suffix.lower() or ".img"
    target = target_dir / f"source{suffix}"
    shutil.copy2(source_file, target)

    relative_path = target.relative_to(PROJECT_ROOT).as_posix()
    name = str(display_name or "").strip() or source_file.stem
    source_kind = str(source or "local").strip() or "local"

    try:
        file_size = target.stat().st_size

        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO image_assets(
                    id,
                    display_name,
                    local_path,
                    original_filename,
                    content_type,
                    file_size,
                    source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    asset_id,
                    name,
                    relative_path,
                    source_file.name,
                    content_type,
                    file_size,
                    source_kind,
                ),
            )
    except Exception:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise

    return asset_id


def get_image_asset(image_id: str):
    image_id = str(image_id or "").strip()

    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM image_assets
            WHERE id = ?
            """,
            (image_id,),
        ).fetchone()


def get_image_asset_bundle(image_id: str) -> dict:
    image_id = str(image_id or "").strip()

    with get_connection() as conn:
        asset = conn.execute(
            """
            SELECT *
            FROM image_assets
            WHERE id = ?
            """,
            (image_id,),
        ).fetchone()

        if asset is None:
            raise ValueError("画像が見つかりません。")

        tags = conn.execute(
            """
            SELECT t.id, t.name
            FROM image_tags t
            JOIN image_asset_tags iat
              ON iat.tag_id = t.id
            WHERE iat.image_id = ?
            ORDER BY t.name COLLATE NOCASE ASC
            """,
            (image_id,),
        ).fetchall()

        group_ids = [
            row["group_id"]
            for row in conn.execute(
                """
                SELECT group_id
                FROM image_asset_groups
                WHERE image_id = ?
                """,
                (image_id,),
            ).fetchall()
        ]

    return {
        "asset": dict(asset),
        "tags": [dict(row) for row in tags],
        "group_ids": group_ids,
    }


# IMAGES_PERF_PAGINATED_QUERY
def list_image_assets(
    search_text: str = "",
    search_mode: str = "keyword",
    group_id: str | None = None,
    only_ungrouped: bool = False,
    only_untagged: bool = False,
    limit: int | None = None,
    offset: int = 0,
):
    search_text = str(search_text or "").strip()
    search_mode = str(search_mode or "keyword").strip().lower()
    group_id = str(group_id or "").strip() or None

    if limit is not None:
        limit = max(1, min(int(limit), 1000))

    offset = max(0, int(offset or 0))

    if group_id is not None and only_ungrouped:
        raise ValueError(
            "グループ指定と「未分類」は同時に指定できません。"
        )

    conditions = ["1 = 1"]
    params: list[object] = []

    if only_ungrouped:
        conditions.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM image_asset_groups iag
                WHERE iag.image_id = a.id
            )
            """
        )

    if only_untagged:
        conditions.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM image_asset_tags iat
                WHERE iat.image_id = a.id
            )
            """
        )

    if search_text:
        if search_mode == "tag":
            for term in _parse_tag_search(search_text):
                conditions.append(
                    """
                    EXISTS (
                        SELECT 1
                        FROM image_asset_tags iat
                        JOIN image_tags t
                          ON t.id = iat.tag_id
                        WHERE iat.image_id = a.id
                          AND t.name LIKE ?
                    )
                    """
                )
                params.append(f"%{term}%")
        else:
            needle = f"%{search_text}%"
            conditions.append(
                """
                (
                    a.display_name LIKE ?
                    OR a.original_filename LIKE ?
                )
                """
            )
            params.extend([needle, needle])

    where_sql = " AND ".join(conditions)

    group_condition = ""
    cte = ""
    query_params: list[object] = list(params)

    if group_id is not None:
        cte = """
            WITH RECURSIVE descendants(id) AS (
                SELECT ?
                UNION ALL
                SELECT g.id
                FROM image_groups g
                JOIN descendants d
                  ON g.parent_group_id = d.id
            )
        """
        group_condition = """
              AND EXISTS (
                    SELECT 1
                    FROM image_asset_groups iag
                    JOIN descendants d
                      ON d.id = iag.group_id
                    WHERE iag.image_id = a.id
              )
        """
        query_params = [group_id, *params]

    sql = f"""
        {cte}
        SELECT
            a.*,
            COUNT(*) OVER () AS total_count,
            (
                SELECT COUNT(*)
                FROM image_asset_tags iat
                WHERE iat.image_id = a.id
            ) AS tag_count,
            (
                SELECT COUNT(*)
                FROM image_asset_groups iag
                WHERE iag.image_id = a.id
            ) AS group_count,
            CASE
                WHEN COALESCE(a.ccfolia_url, '') <> ''
                THEN 1
                ELSE 0
            END AS ccfolia_registered
        FROM image_assets a
        WHERE {where_sql}
        {group_condition}
        ORDER BY
            a.display_name COLLATE NOCASE ASC,
            a.id ASC
    """

    if limit is not None:
        sql += "\n LIMIT ? OFFSET ?"
        query_params.extend([limit, offset])

    with get_connection() as conn:
        return conn.execute(sql, query_params).fetchall()


def list_ungrouped_image_assets(
    search_text: str = "",
    search_mode: str = "keyword",
):
    return list_image_assets(
        search_text=search_text,
        search_mode=search_mode,
        only_ungrouped=True,
    )


def list_untagged_image_assets(
    search_text: str = "",
    search_mode: str = "keyword",
    group_id: str | None = None,
):
    return list_image_assets(
        search_text=search_text,
        search_mode=search_mode,
        group_id=group_id,
        only_untagged=True,
    )


def rename_image_asset(
    image_id: str,
    display_name: str,
) -> None:
    image_id = str(image_id or "").strip()
    display_name = str(display_name or "").strip()

    if not display_name:
        raise ValueError("画像名を入力してください。")

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE image_assets
            SET
                display_name = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (display_name, image_id),
        )

        if result.rowcount == 0:
            raise ValueError("画像が見つかりません。")


def delete_image_assets(image_ids) -> int:
    ids = _clean_ids(image_ids)
    if not ids:
        return 0

    local_paths: list[str] = []

    with get_connection() as conn:
        for image_id in ids:
            row = conn.execute(
                """
                SELECT local_path
                FROM image_assets
                WHERE id = ?
                """,
                (image_id,),
            ).fetchone()

            if row is None:
                continue

            local_paths.append(str(row["local_path"] or ""))
            conn.execute(
                "DELETE FROM image_assets WHERE id = ?",
                (image_id,),
            )

    root = IMAGE_ASSETS_DIR.resolve()

    for relative in local_paths:
        if not relative:
            continue

        try:
            path = (PROJECT_ROOT / relative).resolve()
            parent = path.parent

            if parent.is_relative_to(root):
                shutil.rmtree(parent, ignore_errors=True)
        except Exception:
            pass

    return len(ids)


def list_image_tags():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, name
            FROM image_tags
            ORDER BY name COLLATE NOCASE ASC
            """
        ).fetchall()


def _get_or_create_tag_ids(
    conn,
    tag_names,
) -> list[str]:
    output = []

    for tag_name in _clean_tag_names(tag_names):
        row = conn.execute(
            """
            SELECT id
            FROM image_tags
            WHERE name = ? COLLATE NOCASE
            """,
            (tag_name,),
        ).fetchone()

        if row is None:
            tag_id = generate_app_id()
            conn.execute(
                """
                INSERT INTO image_tags(id, name)
                VALUES (?, ?)
                """,
                (tag_id, tag_name),
            )
        else:
            tag_id = row["id"]

        output.append(tag_id)

    return output


def set_image_tags(
    image_id: str,
    tag_names,
) -> None:
    image_id = str(image_id or "").strip()

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM image_assets WHERE id = ?",
            (image_id,),
        ).fetchone()

        if exists is None:
            raise ValueError("画像が見つかりません。")

        tag_ids = _get_or_create_tag_ids(
            conn,
            tag_names,
        )

        conn.execute(
            "DELETE FROM image_asset_tags WHERE image_id = ?",
            (image_id,),
        )

        for tag_id in tag_ids:
            conn.execute(
                """
                INSERT OR IGNORE INTO image_asset_tags(
                    image_id,
                    tag_id
                )
                VALUES (?, ?)
                """,
                (image_id, tag_id),
            )

        conn.execute(
            """
            UPDATE image_assets
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (image_id,),
        )


def add_tags_to_images(
    image_ids,
    tag_names,
) -> int:
    ids = _clean_ids(image_ids)
    names = _clean_tag_names(tag_names)

    if not ids or not names:
        return 0

    added = 0

    with get_connection() as conn:
        tag_ids = _get_or_create_tag_ids(
            conn,
            names,
        )

        for image_id in ids:
            exists = conn.execute(
                "SELECT 1 FROM image_assets WHERE id = ?",
                (image_id,),
            ).fetchone()

            if exists is None:
                continue

            for tag_id in tag_ids:
                result = conn.execute(
                    """
                    INSERT OR IGNORE INTO image_asset_tags(
                        image_id,
                        tag_id
                    )
                    VALUES (?, ?)
                    """,
                    (image_id, tag_id),
                )
                if result.rowcount:
                    added += 1

            conn.execute(
                """
                UPDATE image_assets
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (image_id,),
            )

    return added


def list_image_groups():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                id,
                name,
                parent_group_id,
                sort_order
            FROM image_groups
            ORDER BY
                sort_order ASC,
                name COLLATE NOCASE ASC
            """
        ).fetchall()


def create_image_group(
    name: str,
    parent_group_id: str | None = None,
) -> str:
    name = str(name or "").strip()
    if not name:
        raise ValueError("グループ名を入力してください。")

    parent_group_id = (
        str(parent_group_id).strip()
        if parent_group_id is not None
        else None
    )
    if parent_group_id == "":
        parent_group_id = None

    group_id = generate_app_id()

    with get_connection() as conn:
        if parent_group_id is not None:
            parent = conn.execute(
                "SELECT 1 FROM image_groups WHERE id = ?",
                (parent_group_id,),
            ).fetchone()

            if parent is None:
                raise ValueError("親グループが見つかりません。")

        next_order = conn.execute(
            """
            SELECT
                COALESCE(MAX(sort_order), -1) + 1
                AS next_order
            FROM image_groups
            WHERE parent_group_id IS ?
            """,
            (parent_group_id,),
        ).fetchone()["next_order"]

        conn.execute(
            """
            INSERT INTO image_groups(
                id,
                name,
                parent_group_id,
                sort_order
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                group_id,
                name,
                parent_group_id,
                next_order,
            ),
        )

    return group_id


def rename_image_group(
    group_id: str,
    new_name: str,
) -> None:
    group_id = str(group_id or "").strip()
    new_name = str(new_name or "").strip()

    if not new_name:
        raise ValueError("グループ名を入力してください。")

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE image_groups
            SET name = ?
            WHERE id = ?
            """,
            (new_name, group_id),
        )

        if result.rowcount == 0:
            raise ValueError("グループが見つかりません。")


def delete_image_group(group_id: str) -> None:
    group_id = str(group_id or "").strip()

    with get_connection() as conn:
        conn.execute(
            "DELETE FROM image_groups WHERE id = ?",
            (group_id,),
        )


def add_group_to_images(
    image_ids,
    group_id: str,
) -> int:
    ids = _clean_ids(image_ids)
    group_id = str(group_id or "").strip()

    if not ids or not group_id:
        return 0

    added = 0

    with get_connection() as conn:
        group_exists = conn.execute(
            "SELECT 1 FROM image_groups WHERE id = ?",
            (group_id,),
        ).fetchone()

        if group_exists is None:
            raise ValueError("グループが見つかりません。")

        for image_id in ids:
            exists = conn.execute(
                "SELECT 1 FROM image_assets WHERE id = ?",
                (image_id,),
            ).fetchone()

            if exists is None:
                continue

            result = conn.execute(
                """
                INSERT OR IGNORE INTO image_asset_groups(
                    image_id,
                    group_id
                )
                VALUES (?, ?)
                """,
                (image_id, group_id),
            )

            if result.rowcount:
                added += 1

    return added


def set_image_groups(
    image_id: str,
    group_ids,
) -> None:
    image_id = str(image_id or "").strip()
    groups = _clean_ids(group_ids)

    with get_connection() as conn:
        exists = conn.execute(
            "SELECT 1 FROM image_assets WHERE id = ?",
            (image_id,),
        ).fetchone()

        if exists is None:
            raise ValueError("画像が見つかりません。")

        valid_groups = []

        for group_id in groups:
            row = conn.execute(
                "SELECT 1 FROM image_groups WHERE id = ?",
                (group_id,),
            ).fetchone()

            if row is not None:
                valid_groups.append(group_id)

        conn.execute(
            "DELETE FROM image_asset_groups WHERE image_id = ?",
            (image_id,),
        )

        for group_id in valid_groups:
            conn.execute(
                """
                INSERT OR IGNORE INTO image_asset_groups(
                    image_id,
                    group_id
                )
                VALUES (?, ?)
                """,
                (image_id, group_id),
            )


def persist_image_group_tree_structure(
    rows: list[tuple[str, str | None, int]],
) -> None:
    normalized = []

    for group_id, parent_group_id, sort_order in rows:
        group_id = str(group_id or "").strip()
        if not group_id:
            raise ValueError("グループIDが空です。")

        parent = (
            str(parent_group_id).strip()
            if parent_group_id is not None
            else None
        )
        if parent == "":
            parent = None

        normalized.append(
            (
                group_id,
                parent,
                int(sort_order),
            )
        )

    with get_connection() as conn:
        existing = {
            row["id"]
            for row in conn.execute(
                "SELECT id FROM image_groups"
            ).fetchall()
        }

        for group_id, parent_group_id, _sort_order in normalized:
            if group_id not in existing:
                raise ValueError(
                    f"グループが見つかりません: {group_id}"
                )
            if (
                parent_group_id is not None
                and parent_group_id not in existing
            ):
                raise ValueError(
                    f"親グループが見つかりません: {parent_group_id}"
                )

        for group_id, parent_group_id, sort_order in normalized:
            conn.execute(
                """
                UPDATE image_groups
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


def set_ccfolia_registration(
    image_id: str,
    *,
    file_id: str,
    url: str,
    content_type: str = "",
    file_size: int | None = None,
) -> None:
    image_id = str(image_id or "").strip()
    file_id = str(file_id or "").strip()
    url = str(url or "").strip()

    if not file_id:
        raise ValueError("CCFOLIA file IDが空です。")
    if not url:
        raise ValueError("CCFOLIA URLが空です。")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM image_assets WHERE id = ?",
            (image_id,),
        ).fetchone()

        if row is None:
            raise ValueError("画像が見つかりません。")

        conn.execute(
            """
            UPDATE image_assets
            SET
                ccfolia_file_id = ?,
                ccfolia_url = ?,
                content_type = CASE
                    WHEN ? <> '' THEN ?
                    ELSE content_type
                END,
                file_size = CASE
                    WHEN ? IS NOT NULL THEN ?
                    ELSE file_size
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                file_id,
                url,
                str(content_type or ""),
                str(content_type or ""),
                file_size,
                file_size,
                image_id,
            ),
        )


def upsert_salvaged_image(
    *,
    file_id: str,
    url: str,
    content_type: str = "",
    file_size: int = 0,
    display_name: str = "",
) -> tuple[str, bool]:
    file_id = str(file_id or "").strip()
    url = str(url or "").strip()

    if not file_id:
        raise ValueError("CCFOLIA file IDが空です。")
    if not url:
        raise ValueError("CCFOLIA URLが空です。")

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM image_assets
            WHERE ccfolia_file_id = ?
            """,
            (file_id,),
        ).fetchone()

        if existing is not None:
            image_id = existing["id"]
            conn.execute(
                """
                UPDATE image_assets
                SET
                    ccfolia_url = ?,
                    content_type = CASE
                        WHEN ? <> '' THEN ?
                        ELSE content_type
                    END,
                    file_size = CASE
                        WHEN ? > 0 THEN ?
                        ELSE file_size
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    url,
                    str(content_type or ""),
                    str(content_type or ""),
                    int(file_size or 0),
                    int(file_size or 0),
                    image_id,
                ),
            )
            return image_id, False

        image_id = generate_app_id()
        name = (
            str(display_name or "").strip()
            or f"画像 {file_id[:8]}"
        )

        conn.execute(
            """
            INSERT INTO image_assets(
                id,
                display_name,
                ccfolia_file_id,
                ccfolia_url,
                content_type,
                file_size,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, 'ccfolia_salvage')
            """,
            (
                image_id,
                name,
                file_id,
                url,
                str(content_type or ""),
                max(0, int(file_size or 0)),
            ),
        )

    return image_id, True
