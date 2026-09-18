from __future__ import annotations

# BGM_BROWSER_IMPORT_SERVICE_V1

import base64
import binascii
import tempfile
from pathlib import Path

from app.paths import APP_DATA_DIR
from app.services.bgm_service import (
    get_bgm_asset,
    import_bgm_asset,
)


_MAX_AUDIO_BYTES = 64 * 1024 * 1024

_ALLOWED_SUFFIXES = {
    ".mp3",
    ".wav",
    ".ogg",
    ".oga",
    ".m4a",
    ".aac",
    ".flac",
    ".opus",
    ".webm",
}


def import_browser_bgm(
    *,
    filename: str,
    data_base64: str,
    media_kind: str = "bgm",
) -> dict:
    filename = Path(
        str(filename or "audio.mp3")
    ).name

    if not filename:
        filename = "audio.mp3"

    suffix = Path(filename).suffix.lower()

    if suffix not in _ALLOWED_SUFFIXES:
        raise ValueError(
            "対応していない音声形式です。"
        )

    payload = str(
        data_base64 or ""
    ).strip()

    if not payload:
        raise ValueError(
            "音声データが空です。"
        )

    try:
        raw = base64.b64decode(
            payload,
            validate=True,
        )
    except (
        ValueError,
        binascii.Error,
    ) as exc:
        raise ValueError(
            "音声データが不正です。"
        ) from exc

    if not raw:
        raise ValueError(
            "音声データが空です。"
        )

    if len(raw) > _MAX_AUDIO_BYTES:
        raise ValueError(
            "音声ファイルは64MB以下にしてください。"
        )

    APP_DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = None

    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=suffix,
            prefix="bgm_import_",
            dir=APP_DATA_DIR,
            delete=False,
        ) as handle:
            handle.write(raw)
            temporary_path = Path(
                handle.name
            )

        bgm_id, created = import_bgm_asset(
            temporary_path,
            display_name=Path(
                filename
            ).stem,
            media_kind=media_kind,
            source="browser_import",
            deduplicate=True,
        )

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

    row = get_bgm_asset(
        bgm_id
    )

    if row is None:
        raise RuntimeError(
            "取り込んだBGMをDBから取得できませんでした。"
        )

    return {
        "id": str(bgm_id),
        "created": bool(created),
        "display_name": str(
            row["display_name"] or ""
        ),
        "filename": filename,
        "file_size": int(
            row["file_size"] or 0
        ),
        "duration_ms": int(
            row["duration_ms"] or 0
        ),
        "default_volume": float(
            row["default_volume"] or 0
        ),
        "default_loop": bool(
            row["default_loop"]
        ),
        "media_kind": str(
            row["media_kind"] or "bgm"
        ),
        "has_local": bool(
            str(
                row["local_path"] or ""
            ).strip()
        ),
    }

# BGM_BROWSER_PANEL_SERVICE_V1
import base64 as _bgm_panel_base64

from app.paths import BGM_ASSETS_DIR, PROJECT_ROOT
from app.services.bgm_service import (
    get_bgm_asset_bundle,
    list_bgm_assets,
    list_bgm_groups,
    list_bgm_tags,
    set_bgm_tags,
    set_ccfolia_registration,
    update_bgm_asset,
)


def _serialize_browser_bgm(row) -> dict:
    bgm_id = str(row["id"])
    bundle = get_bgm_asset_bundle(bgm_id) or {}

    return {
        "id": bgm_id,
        "display_name": str(
            row["display_name"]
            or row["original_filename"]
            or "BGM"
        ),
        "original_filename": str(row["original_filename"] or ""),
        "content_type": str(row["content_type"] or ""),
        "file_size": int(row["file_size"] or 0),
        "duration_ms": int(row["duration_ms"] or 0),
        "default_volume": float(row["default_volume"] or 0),
        "default_loop": bool(row["default_loop"]),
        "media_kind": str(row["media_kind"] or "bgm"),
        "source": str(row["source"] or ""),
        "has_local": bool(str(row["local_path"] or "").strip()),
        "ccfolia_registered": bool(
            str(row["ccfolia_url"] or "").strip()
        ),
        "ccfolia_media_id": str(row["ccfolia_media_id"] or ""),
        "ccfolia_url": str(row["ccfolia_url"] or ""),
        "ccfolia_dir": str(row["ccfolia_dir"] or ""),
        "ccfolia_order": float(row["ccfolia_order"] or 0),
        "tags": [
            str(tag.get("name") or "")
            for tag in bundle.get("tags", [])
            if str(tag.get("name") or "").strip()
        ],
        "group_ids": [
            str(value)
            for value in bundle.get("group_ids", [])
        ],
    }


def list_browser_bgm_assets(
    *,
    search_text: str = "",
    search_mode: str = "keyword",
    group_id: str | None = None,
    only_ungrouped: bool = False,
    only_untagged: bool = False,
    media_kind: str | None = None,
    page: int = 1,
    page_size: int = 60,
) -> dict:
    rows = list(
        list_bgm_assets(
            search_text=search_text,
            search_mode=search_mode,
            group_id=group_id,
            only_ungrouped=only_ungrouped,
            only_untagged=only_untagged,
            media_kind=media_kind,
        )
    )

    total = len(rows)
    page_size = max(10, min(int(page_size or 60), 120))
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(1, min(int(page or 1), pages))
    start = (page - 1) * page_size
    sliced = rows[start:start + page_size]

    return {
        "assets": [
            _serialize_browser_bgm(row)
            for row in sliced
        ],
        "total": total,
        "page": page,
        "pages": pages,
        "page_size": page_size,
    }


def browser_bgm_tags() -> list[dict]:
    return [
        {
            "id": str(row["id"]),
            "name": str(row["name"] or ""),
        }
        for row in list_bgm_tags()
    ]


def browser_bgm_groups() -> list[dict]:
    return [
        {
            "id": str(row["id"]),
            "name": str(row["name"] or ""),
            "parent_group_id": (
                str(row["parent_group_id"])
                if row["parent_group_id"] is not None
                else None
            ),
            "sort_order": int(row["sort_order"] or 0),
        }
        for row in list_bgm_groups()
    ]


def get_browser_bgm_upload_source(bgm_id: str) -> dict:
    row = get_bgm_asset(bgm_id)

    if row is None:
        raise ValueError("BGMが見つかりません。")

    relative = str(row["local_path"] or "").strip()
    if not relative:
        raise ValueError("ローカル音源がありません。")

    path = (PROJECT_ROOT / relative).resolve()
    root = BGM_ASSETS_DIR.resolve()

    if not path.is_relative_to(root):
        raise ValueError("BGMの保存場所が不正です。")
    if not path.is_file():
        raise ValueError("ローカル音源ファイルが見つかりません。")

    raw = path.read_bytes()
    if len(raw) > 64 * 1024 * 1024:
        raise ValueError("音声ファイルは64MB以下にしてください。")

    return {
        "id": str(row["id"]),
        "filename": str(row["original_filename"] or path.name),
        "content_type": str(row["content_type"] or "audio/mpeg"),
        "data_base64": _bgm_panel_base64.b64encode(raw).decode("ascii"),
        "display_name": str(row["display_name"] or path.stem),
        "default_volume": float(row["default_volume"] or 0),
        "default_loop": bool(row["default_loop"]),
        "media_kind": str(row["media_kind"] or "bgm"),
    }


def register_browser_bgm_ccfolia(
    *,
    bgm_id: str,
    media_id: str,
    url: str,
    directory: str = "bgm01",
    order: float = 0,
    updated_at: int | None = None,
) -> dict:
    set_ccfolia_registration(
        bgm_id,
        media_id=media_id,
        url=url,
        directory=directory,
        order=order,
        uploaded=True,
        archived=False,
        ccfolia_updated_at=updated_at,
    )

    row = get_bgm_asset(bgm_id)
    if row is None:
        raise ValueError("BGMが見つかりません。")

    return _serialize_browser_bgm(row)


def update_browser_bgm(
    *,
    bgm_id: str,
    display_name: str,
    default_volume,
    default_loop,
    media_kind: str,
    tags,
) -> dict:
    update_bgm_asset(
        bgm_id,
        display_name=display_name,
        default_volume=default_volume,
        default_loop=bool(default_loop),
        media_kind=media_kind,
    )
    set_bgm_tags(bgm_id, tags or [])

    row = get_bgm_asset(bgm_id)
    if row is None:
        raise ValueError("BGMが見つかりません。")

    return _serialize_browser_bgm(row)

# BGM_SALVAGE_SERVICE_V1
def salvage_browser_bgm_items(*, items, tab_labels=None) -> dict:
    from app.services.bgm_service import (
        add_tags_to_bgm,
        upsert_salvaged_bgm,
    )

    labels = {
        str(key or "").strip(): str(value or "").strip()
        for key, value in dict(tab_labels or {}).items()
        if str(key or "").strip()
        and str(value or "").strip()
    }

    result = {
        "received": 0,
        "created": 0,
        "updated": 0,
        "tagged": 0,
        "skipped_archived": 0,
        "skipped_invalid": 0,
        "errors": [],
    }

    for index, item in enumerate(items or [], start=1):
        result["received"] += 1

        try:
            if not isinstance(item, dict):
                result["skipped_invalid"] += 1
                continue

            if bool(item.get("archived", False)):
                result["skipped_archived"] += 1
                continue

            media_id = str(item.get("id") or "").strip()
            url = str(item.get("url") or "").strip()

            if not media_id or not url:
                result["skipped_invalid"] += 1
                continue

            directory = str(item.get("dir") or "").strip()

            bgm_id, created = upsert_salvaged_bgm(
                media_id=media_id,
                url=url,
                display_name=str(item.get("name") or "").strip(),
                content_type=str(
                    item.get("contentType") or ""
                ).strip(),
                file_size=max(
                    0,
                    int(item.get("size") or 0),
                ),
                directory=directory,
                order=float(item.get("order") or 0),
                volume=float(
                    item.get("volume")
                    if item.get("volume") is not None
                    else 0.5
                ),
                loop=bool(
                    item.get("loop")
                    if item.get("loop") is not None
                    else True
                ),
                uploaded=bool(
                    item.get("uploaded")
                    if item.get("uploaded") is not None
                    else True
                ),
                archived=False,
                ccfolia_updated_at=(
                    int(item.get("updatedAt"))
                    if item.get("updatedAt") is not None
                    else None
                ),
                raw=item,
            )

            if created:
                result["created"] += 1
            else:
                result["updated"] += 1

            tab_name = labels.get(directory, "")

            if tab_name:
                added = add_tags_to_bgm(
                    [bgm_id],
                    [tab_name],
                )
                if added:
                    result["tagged"] += 1

        except Exception as exc:
            if len(result["errors"]) < 50:
                result["errors"].append(
                    {
                        "index": index,
                        "media_id": (
                            str(item.get("id") or "")
                            if isinstance(item, dict)
                            else ""
                        ),
                        "error": str(exc),
                    }
                )

    return result

# BGM_FIXED_TAB_SLOTS_SERVICE_V1
def _bgm_fixed_slot_tag(slot_index: int) -> str:
    return f"BGM{int(slot_index):02d}"


def _bgm_ensure_slot_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bgm_dir_slots (
            dir_id TEXT PRIMARY KEY,
            slot_index INTEGER NOT NULL UNIQUE
                CHECK(slot_index BETWEEN 1 AND 10),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_bgm_dir_slots_slot
        ON bgm_dir_slots(slot_index)
        """
    )


def _bgm_fixed_slot_mapping(conn) -> dict[str, int]:
    _bgm_ensure_slot_table(conn)

    return {
        str(row["dir_id"]): int(row["slot_index"])
        for row in conn.execute(
            """
            SELECT dir_id, slot_index
            FROM bgm_dir_slots
            ORDER BY slot_index ASC
            """
        ).fetchall()
    }


def _bgm_ensure_fixed_slots(
    conn,
    dir_ids,
) -> tuple[dict[str, int], list[str]]:
    _bgm_ensure_slot_table(conn)

    ordered: list[str] = []
    seen: set[str] = set()

    for value in dir_ids or []:
        directory = str(value or "").strip()

        if not directory or directory in seen:
            continue

        seen.add(directory)
        ordered.append(directory)

    mapping = _bgm_fixed_slot_mapping(conn)
    used = set(mapping.values())
    overflow: list[str] = []

    for directory in ordered:
        if directory in mapping:
            continue

        free_slot = next(
            (
                slot
                for slot in range(1, 11)
                if slot not in used
            ),
            None,
        )

        if free_slot is None:
            overflow.append(directory)
            continue

        conn.execute(
            """
            INSERT INTO bgm_dir_slots(
                dir_id,
                slot_index
            )
            VALUES (?, ?)
            """,
            (
                directory,
                free_slot,
            ),
        )

        mapping[directory] = free_slot
        used.add(free_slot)

    return mapping, overflow


def _bgm_cleanup_and_apply_fixed_slot_tags(
    conn,
    mapping: dict[str, int],
) -> int:
    legacy_names = [
        *[
            f"BGM{slot:02d}"
            for slot in range(1, 11)
        ],
        *[
            f"SE{slot:02d}"
            for slot in range(1, 11)
        ],
        "その他",
    ]

    placeholders = ",".join(
        "?" for _ in legacy_names
    )

    conn.execute(
        f"""
        DELETE FROM bgm_asset_tags
        WHERE
            bgm_id IN (
                SELECT id
                FROM bgm_assets
                WHERE
                    ccfolia_media_id IS NOT NULL
                    AND ccfolia_media_id <> ''
            )
            AND tag_id IN (
                SELECT id
                FROM bgm_tags
                WHERE name IN ({placeholders})
            )
        """,
        legacy_names,
    )

    tagged = 0

    for directory, slot_index in sorted(
        mapping.items(),
        key=lambda pair: pair[1],
    ):
        tag_name = _bgm_fixed_slot_tag(
            slot_index
        )

        row = conn.execute(
            """
            SELECT id
            FROM bgm_tags
            WHERE name = ? COLLATE NOCASE
            LIMIT 1
            """,
            (tag_name,),
        ).fetchone()

        if row is None:
            from app.ids import generate_app_id

            tag_id = generate_app_id()

            conn.execute(
                """
                INSERT INTO bgm_tags(
                    id,
                    name
                )
                VALUES (?, ?)
                """,
                (
                    tag_id,
                    tag_name,
                ),
            )
        else:
            tag_id = str(row["id"])

        asset_rows = conn.execute(
            """
            SELECT id
            FROM bgm_assets
            WHERE
                ccfolia_media_id IS NOT NULL
                AND ccfolia_media_id <> ''
                AND ccfolia_dir = ?
            """,
            (directory,),
        ).fetchall()

        for asset_row in asset_rows:
            inserted = conn.execute(
                """
                INSERT OR IGNORE
                INTO bgm_asset_tags(
                    bgm_id,
                    tag_id
                )
                VALUES (?, ?)
                """,
                (
                    str(asset_row["id"]),
                    tag_id,
                ),
            )

            tagged += max(
                0,
                int(inserted.rowcount),
            )

    conn.execute(
        f"""
        DELETE FROM bgm_tags
        WHERE
            name IN ({placeholders})
            AND NOT EXISTS (
                SELECT 1
                FROM bgm_asset_tags
                WHERE bgm_asset_tags.tag_id
                    = bgm_tags.id
            )
        """,
        legacy_names,
    )

    return tagged


def reset_fixed_bgm_slot_mapping() -> dict:
    from app.db.database import get_connection

    with get_connection() as conn:
        _bgm_ensure_slot_table(conn)

        conn.execute(
            "DELETE FROM bgm_dir_slots"
        )

        rows = conn.execute(
            """
            SELECT
                ccfolia_dir,
                MIN(rowid) AS first_row
            FROM bgm_assets
            WHERE
                ccfolia_media_id IS NOT NULL
                AND ccfolia_media_id <> ''
                AND TRIM(
                    COALESCE(
                        ccfolia_dir,
                        ''
                    )
                ) <> ''
            GROUP BY ccfolia_dir
            ORDER BY first_row ASC
            LIMIT 10
            """
        ).fetchall()

        for index, row in enumerate(
            rows,
            start=1,
        ):
            conn.execute(
                """
                INSERT INTO bgm_dir_slots(
                    dir_id,
                    slot_index
                )
                VALUES (?, ?)
                """,
                (
                    str(row["ccfolia_dir"]),
                    index,
                ),
            )

        mapping = _bgm_fixed_slot_mapping(
            conn
        )

        tagged = (
            _bgm_cleanup_and_apply_fixed_slot_tags(
                conn,
                mapping,
            )
        )

    return {
        "tagged": tagged,
        "mapping": [
            {
                "dir_id": directory,
                "slot_index": slot,
                "tag": _bgm_fixed_slot_tag(slot),
            }
            for directory, slot in sorted(
                mapping.items(),
                key=lambda pair: pair[1],
            )
        ],
    }


def fixed_bgm_slot_mapping() -> list[dict]:
    from app.db.database import get_connection

    with get_connection() as conn:
        mapping = _bgm_fixed_slot_mapping(
            conn
        )

    return [
        {
            "dir_id": directory,
            "slot_index": slot,
            "tag": _bgm_fixed_slot_tag(slot),
        }
        for directory, slot in sorted(
            mapping.items(),
            key=lambda pair: pair[1],
        )
    ]


def salvage_browser_bgm_items(
    *,
    items,
    tab_labels=None,
) -> dict:
    from app.db.database import get_connection
    from app.services.bgm_service import (
        upsert_salvaged_bgm,
    )

    result = {
        "received": 0,
        "created": 0,
        "updated": 0,
        "tagged": 0,
        "slot_count": 0,
        "slot_mapping": [],
        "overflow_dirs": [],
        "skipped_archived": 0,
        "skipped_invalid": 0,
        "errors": [],
    }

    active_dirs: list[str] = []
    active_dir_seen: set[str] = set()

    for index, item in enumerate(
        items or [],
        start=1,
    ):
        result["received"] += 1

        try:
            if not isinstance(item, dict):
                result["skipped_invalid"] += 1
                continue

            if bool(item.get("archived", False)):
                result["skipped_archived"] += 1
                continue

            media_id = str(
                item.get("id") or ""
            ).strip()
            url = str(
                item.get("url") or ""
            ).strip()

            if not media_id or not url:
                result["skipped_invalid"] += 1
                continue

            directory = str(
                item.get("dir") or ""
            ).strip()

            if (
                directory
                and directory not in active_dir_seen
            ):
                active_dir_seen.add(directory)
                active_dirs.append(directory)

            _bgm_id, created = (
                upsert_salvaged_bgm(
                    media_id=media_id,
                    url=url,
                    display_name=str(
                        item.get("name") or ""
                    ).strip(),
                    content_type=str(
                        item.get("contentType")
                        or ""
                    ).strip(),
                    file_size=max(
                        0,
                        int(item.get("size") or 0),
                    ),
                    directory=directory,
                    order=float(
                        item.get("order") or 0
                    ),
                    volume=float(
                        item.get("volume")
                        if item.get("volume") is not None
                        else 0.5
                    ),
                    loop=bool(
                        item.get("loop")
                        if item.get("loop") is not None
                        else True
                    ),
                    uploaded=bool(
                        item.get("uploaded")
                        if item.get("uploaded") is not None
                        else True
                    ),
                    archived=False,
                    ccfolia_updated_at=(
                        int(item.get("updatedAt"))
                        if item.get("updatedAt") is not None
                        else None
                    ),
                    raw=item,
                )
            )

            if created:
                result["created"] += 1
            else:
                result["updated"] += 1

        except Exception as exc:
            if len(result["errors"]) < 50:
                result["errors"].append(
                    {
                        "index": index,
                        "media_id": (
                            str(item.get("id") or "")
                            if isinstance(item, dict)
                            else ""
                        ),
                        "error": str(exc),
                    }
                )

    with get_connection() as conn:
        mapping, overflow = (
            _bgm_ensure_fixed_slots(
                conn,
                active_dirs,
            )
        )

        tagged = (
            _bgm_cleanup_and_apply_fixed_slot_tags(
                conn,
                mapping,
            )
        )

        result["tagged"] = tagged
        result["slot_count"] = len(
            mapping
        )
        result["overflow_dirs"] = (
            overflow
        )
        result["slot_mapping"] = [
            {
                "dir_id": directory,
                "slot_index": slot,
                "tag":
                    _bgm_fixed_slot_tag(
                        slot
                    ),
            }
            for directory, slot
            in sorted(
                mapping.items(),
                key=lambda pair:
                    pair[1],
            )
        ]

    return result
