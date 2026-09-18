from __future__ import annotations

# BGM_MODULE_SERVICE_V1

import hashlib
import json
import mimetypes
import shutil
import wave
from pathlib import Path

from app.db.database import get_connection
from app.ids import generate_app_id
from app.paths import BGM_ASSETS_DIR, PROJECT_ROOT


_AUDIO_CONTENT_TYPES = {
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".oga": "audio/ogg",
    ".m4a": "audio/x-m4a",
    ".aac": "audio/aac",
    ".flac": "audio/flac",
    ".opus": "audio/ogg",
    ".webm": "audio/webm",
}

_ALLOWED_MEDIA_KINDS = {
    "bgm",
    "se",
    "other",
}


def _clean_ids(values) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for value in values or []:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        output.append(item)

    return output


def _clean_tag_names(values) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for value in values or []:
        name = str(value or "").strip()
        key = name.casefold()

        if not name or key in seen:
            continue

        seen.add(key)
        output.append(name)

    return output


def _normalize_media_kind(value: str) -> str:
    media_kind = str(value or "bgm").strip().lower()

    if media_kind not in _ALLOWED_MEDIA_KINDS:
        raise ValueError(
            "media_kind は bgm / se / other のいずれかを指定してください。"
        )

    return media_kind


def _normalize_volume(value) -> float:
    try:
        volume = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("音量は0〜1の数値で指定してください。") from exc

    if not 0.0 <= volume <= 1.0:
        raise ValueError("音量は0〜1の範囲で指定してください。")

    return volume


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()

    if suffix in _AUDIO_CONTENT_TYPES:
        return _AUDIO_CONTENT_TYPES[suffix]

    guessed, _encoding = mimetypes.guess_type(path.name)
    return guessed or ""


def _require_audio_file(
    source_path: str | Path,
) -> tuple[Path, str]:
    source = Path(source_path).expanduser().resolve()

    if not source.is_file():
        raise ValueError("音声ファイルが見つかりません。")

    content_type = _guess_content_type(source)

    if (
        source.suffix.lower() not in _AUDIO_CONTENT_TYPES
        and not content_type.startswith("audio/")
    ):
        raise ValueError("対応している音声ファイルを選択してください。")

    return source, content_type


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


def _probe_duration_ms(path: Path) -> int:
    if path.suffix.lower() == ".wav":
        try:
            with wave.open(str(path), "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()

                if rate > 0:
                    return max(
                        0,
                        int(round(frames * 1000 / rate)),
                    )
        except Exception:
            pass

    try:
        import mutagen  # type: ignore

        audio = mutagen.File(str(path))

        if (
            audio is not None
            and getattr(audio, "info", None) is not None
        ):
            seconds = float(
                getattr(audio.info, "length", 0.0)
                or 0.0
            )
            return max(
                0,
                int(round(seconds * 1000)),
            )
    except Exception:
        pass

    return 0


def _safe_local_path(
    relative_path: str,
) -> Path | None:
    value = str(relative_path or "").strip()

    if not value:
        return None

    try:
        path = (PROJECT_ROOT / value).resolve()
        root = BGM_ASSETS_DIR.resolve()

        if not path.is_relative_to(root):
            return None

        if not path.is_file():
            return None

        return path
    except Exception:
        return None


def _find_by_hash(
    conn,
    content_sha256: str,
):
    if not content_sha256:
        return None

    return conn.execute(
        """
        SELECT *
        FROM bgm_assets
        WHERE content_sha256 = ?
        ORDER BY
            CASE
                WHEN local_path <> '' THEN 0
                ELSE 1
            END,
            created_at ASC
        LIMIT 1
        """,
        (content_sha256,),
    ).fetchone()


def get_bgm_asset(
    bgm_id: str,
):
    bgm_id = str(bgm_id or "").strip()

    with get_connection() as conn:
        return conn.execute(
            """
            SELECT *
            FROM bgm_assets
            WHERE id = ?
            """,
            (bgm_id,),
        ).fetchone()


def get_bgm_asset_bundle(
    bgm_id: str,
) -> dict | None:
    bgm_id = str(bgm_id or "").strip()

    with get_connection() as conn:
        asset = conn.execute(
            """
            SELECT *
            FROM bgm_assets
            WHERE id = ?
            """,
            (bgm_id,),
        ).fetchone()

        if asset is None:
            return None

        tags = conn.execute(
            """
            SELECT
                t.id,
                t.name
            FROM bgm_tags AS t
            JOIN bgm_asset_tags AS bt
              ON bt.tag_id = t.id
            WHERE bt.bgm_id = ?
            ORDER BY t.name COLLATE NOCASE ASC
            """,
            (bgm_id,),
        ).fetchall()

        group_ids = [
            row["group_id"]
            for row in conn.execute(
                """
                SELECT group_id
                FROM bgm_asset_groups
                WHERE bgm_id = ?
                """,
                (bgm_id,),
            ).fetchall()
        ]

    return {
        "asset": dict(asset),
        "tags": [dict(row) for row in tags],
        "group_ids": group_ids,
    }


def import_bgm_asset(
    source_path: str | Path,
    *,
    display_name: str = "",
    media_kind: str = "bgm",
    default_volume: float = 0.5,
    default_loop: bool = True,
    source: str = "local",
    deduplicate: bool = True,
) -> tuple[str, bool]:
    source_file, content_type = _require_audio_file(
        source_path
    )
    media_kind = _normalize_media_kind(media_kind)
    volume = _normalize_volume(default_volume)
    loop = 1 if bool(default_loop) else 0
    source_kind = (
        str(source or "local").strip()
        or "local"
    )

    content_sha256 = _sha256_file(source_file)
    file_size = source_file.stat().st_size
    duration_ms = _probe_duration_ms(source_file)

    if deduplicate:
        with get_connection() as conn:
            existing = _find_by_hash(
                conn,
                content_sha256,
            )

        if existing is not None:
            existing_id = str(existing["id"])
            existing_path = _safe_local_path(
                str(existing["local_path"] or "")
            )

            if existing_path is not None:
                return existing_id, False

            target_dir = (
                BGM_ASSETS_DIR / existing_id
            )
            target_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

            suffix = (
                source_file.suffix.lower()
                or ".audio"
            )
            target = target_dir / f"source{suffix}"
            temporary = (
                target_dir / f".source{suffix}.tmp"
            )

            shutil.copy2(
                source_file,
                temporary,
            )
            temporary.replace(target)

            relative_path = (
                target.relative_to(PROJECT_ROOT)
                .as_posix()
            )

            with get_connection() as conn:
                conn.execute(
                    """
                    UPDATE bgm_assets
                    SET
                        local_path = ?,
                        original_filename = CASE
                            WHEN original_filename = ''
                            THEN ?
                            ELSE original_filename
                        END,
                        content_type = ?,
                        file_size = ?,
                        duration_ms = CASE
                            WHEN ? > 0 THEN ?
                            ELSE duration_ms
                        END,
                        content_sha256 = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (
                        relative_path,
                        source_file.name,
                        content_type,
                        file_size,
                        duration_ms,
                        duration_ms,
                        content_sha256,
                        existing_id,
                    ),
                )

            return existing_id, False

    bgm_id = generate_app_id()
    target_dir = BGM_ASSETS_DIR / bgm_id
    target_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    suffix = source_file.suffix.lower() or ".audio"
    target = target_dir / f"source{suffix}"
    temporary = target_dir / f".source{suffix}.tmp"

    shutil.copy2(
        source_file,
        temporary,
    )
    temporary.replace(target)

    relative_path = (
        target.relative_to(PROJECT_ROOT)
        .as_posix()
    )
    name = (
        str(display_name or "").strip()
        or source_file.stem
    )

    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO bgm_assets(
                    id,
                    display_name,
                    local_path,
                    original_filename,
                    content_type,
                    file_size,
                    content_sha256,
                    duration_ms,
                    default_volume,
                    default_loop,
                    media_kind,
                    source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bgm_id,
                    name,
                    relative_path,
                    source_file.name,
                    content_type,
                    file_size,
                    content_sha256,
                    duration_ms,
                    volume,
                    loop,
                    media_kind,
                    source_kind,
                ),
            )
    except Exception:
        shutil.rmtree(
            target_dir,
            ignore_errors=True,
        )
        raise

    return bgm_id, True


def import_bgm_assets(
    source_paths,
    *,
    media_kind: str = "bgm",
    default_volume: float = 0.5,
    default_loop: bool = True,
    deduplicate: bool = True,
) -> dict:
    media_kind = _normalize_media_kind(
        media_kind
    )
    volume = _normalize_volume(
        default_volume
    )

    result = {
        "received": 0,
        "created": 0,
        "duplicates": 0,
        "errors": [],
        "ids": [],
    }

    for index, source_path in enumerate(
        source_paths or [],
        start=1,
    ):
        result["received"] += 1

        try:
            bgm_id, created = import_bgm_asset(
                source_path,
                media_kind=media_kind,
                default_volume=volume,
                default_loop=default_loop,
                deduplicate=deduplicate,
            )

            result["ids"].append(bgm_id)

            if created:
                result["created"] += 1
            else:
                result["duplicates"] += 1

        except Exception as exc:
            if len(result["errors"]) < 50:
                result["errors"].append(
                    {
                        "index": index,
                        "path": str(source_path),
                        "error": str(exc),
                    }
                )

    return result


def list_bgm_assets(
    search_text: str = "",
    search_mode: str = "keyword",
    group_id: str | None = None,
    only_ungrouped: bool = False,
    only_untagged: bool = False,
    media_kind: str | None = None,
):
    search_text = str(search_text or "").strip()
    search_mode = (
        str(search_mode or "keyword")
        .strip()
        .lower()
    )
    group_id = (
        str(group_id or "").strip()
        or None
    )

    if group_id is not None and only_ungrouped:
        raise ValueError(
            "グループ指定と「未分類」は同時に指定できません。"
        )

    conditions = ["1 = 1"]
    params: list[object] = []

    if media_kind:
        conditions.append(
            "a.media_kind = ?"
        )
        params.append(
            _normalize_media_kind(media_kind)
        )

    if only_ungrouped:
        conditions.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM bgm_asset_groups AS bag0
                WHERE bag0.bgm_id = a.id
            )
            """
        )
    elif group_id is not None:
        conditions.append(
            """
            EXISTS (
                SELECT 1
                FROM bgm_asset_groups AS bag1
                WHERE
                    bag1.bgm_id = a.id
                    AND bag1.group_id = ?
            )
            """
        )
        params.append(group_id)

    if only_untagged:
        conditions.append(
            """
            NOT EXISTS (
                SELECT 1
                FROM bgm_asset_tags AS bat0
                WHERE bat0.bgm_id = a.id
            )
            """
        )

    if search_text:
        pattern = f"%{search_text}%"

        if search_mode == "tag":
            conditions.append(
                """
                EXISTS (
                    SELECT 1
                    FROM bgm_asset_tags AS bat1
                    JOIN bgm_tags AS t1
                      ON t1.id = bat1.tag_id
                    WHERE
                        bat1.bgm_id = a.id
                        AND t1.name LIKE ?
                )
                """
            )
            params.append(pattern)
        else:
            conditions.append(
                """
                (
                    a.display_name LIKE ?
                    OR a.original_filename LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM bgm_asset_tags AS bat2
                        JOIN bgm_tags AS t2
                          ON t2.id = bat2.tag_id
                        WHERE
                            bat2.bgm_id = a.id
                            AND t2.name LIKE ?
                    )
                )
                """
            )
            params.extend(
                [
                    pattern,
                    pattern,
                    pattern,
                ]
            )

    where_sql = "\n AND ".join(
        conditions
    )

    with get_connection() as conn:
        return conn.execute(
            f"""
            SELECT
                a.*,
                EXISTS (
                    SELECT 1
                    FROM bgm_asset_tags AS bat3
                    WHERE bat3.bgm_id = a.id
                ) AS has_tags,
                EXISTS (
                    SELECT 1
                    FROM bgm_asset_groups AS bag3
                    WHERE bag3.bgm_id = a.id
                ) AS has_groups
            FROM bgm_assets AS a
            WHERE {where_sql}
            ORDER BY
                a.display_name COLLATE NOCASE ASC,
                a.created_at ASC
            """,
            params,
        ).fetchall()


def update_bgm_asset(
    bgm_id: str,
    *,
    display_name: str,
    default_volume: float,
    default_loop: bool,
    media_kind: str = "bgm",
) -> None:
    bgm_id = str(bgm_id or "").strip()
    display_name = str(
        display_name or ""
    ).strip()

    if not display_name:
        raise ValueError(
            "BGM名を入力してください。"
        )

    volume = _normalize_volume(
        default_volume
    )
    kind = _normalize_media_kind(
        media_kind
    )

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE bgm_assets
            SET
                display_name = ?,
                default_volume = ?,
                default_loop = ?,
                media_kind = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                display_name,
                volume,
                1 if bool(default_loop) else 0,
                kind,
                bgm_id,
            ),
        )

        if result.rowcount == 0:
            raise ValueError(
                "BGMが見つかりません。"
            )


def delete_bgm_assets(
    bgm_ids,
) -> int:
    ids = _clean_ids(bgm_ids)

    if not ids:
        return 0

    local_dirs: list[Path] = []

    with get_connection() as conn:
        for bgm_id in ids:
            row = conn.execute(
                """
                SELECT local_path
                FROM bgm_assets
                WHERE id = ?
                """,
                (bgm_id,),
            ).fetchone()

            if row is None:
                continue

            local_path = _safe_local_path(
                str(row["local_path"] or "")
            )

            if local_path is not None:
                local_dirs.append(
                    local_path.parent
                )

        placeholders = ",".join(
            "?" for _ in ids
        )

        result = conn.execute(
            f"""
            DELETE FROM bgm_assets
            WHERE id IN ({placeholders})
            """,
            ids,
        )

        deleted = int(result.rowcount)

    root = BGM_ASSETS_DIR.resolve()

    for directory in local_dirs:
        try:
            resolved = directory.resolve()

            if (
                resolved != root
                and resolved.is_relative_to(root)
            ):
                shutil.rmtree(
                    resolved,
                    ignore_errors=True,
                )
        except Exception:
            pass

    return deleted


def list_bgm_tags():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT id, name
            FROM bgm_tags
            ORDER BY name COLLATE NOCASE ASC
            """
        ).fetchall()


def _get_or_create_tag_ids(
    conn,
    tag_names,
) -> list[str]:
    output: list[str] = []

    for tag_name in _clean_tag_names(
        tag_names
    ):
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
            tag_id = generate_app_id()

            conn.execute(
                """
                INSERT INTO bgm_tags(id, name)
                VALUES (?, ?)
                """,
                (
                    tag_id,
                    tag_name,
                ),
            )
        else:
            tag_id = str(row["id"])

        output.append(tag_id)

    return output


def set_bgm_tags(
    bgm_id: str,
    tag_names,
) -> None:
    bgm_id = str(bgm_id or "").strip()

    with get_connection() as conn:
        exists = conn.execute(
            """
            SELECT 1
            FROM bgm_assets
            WHERE id = ?
            """,
            (bgm_id,),
        ).fetchone()

        if exists is None:
            raise ValueError(
                "BGMが見つかりません。"
            )

        tag_ids = _get_or_create_tag_ids(
            conn,
            tag_names,
        )

        conn.execute(
            """
            DELETE FROM bgm_asset_tags
            WHERE bgm_id = ?
            """,
            (bgm_id,),
        )

        for tag_id in tag_ids:
            conn.execute(
                """
                INSERT INTO bgm_asset_tags(
                    bgm_id,
                    tag_id
                )
                VALUES (?, ?)
                """,
                (
                    bgm_id,
                    tag_id,
                ),
            )


def add_tags_to_bgm(
    bgm_ids,
    tag_names,
) -> int:
    ids = _clean_ids(bgm_ids)
    names = _clean_tag_names(
        tag_names
    )

    if not ids or not names:
        return 0

    added = 0

    with get_connection() as conn:
        tag_ids = _get_or_create_tag_ids(
            conn,
            names,
        )

        for bgm_id in ids:
            exists = conn.execute(
                """
                SELECT 1
                FROM bgm_assets
                WHERE id = ?
                """,
                (bgm_id,),
            ).fetchone()

            if exists is None:
                continue

            for tag_id in tag_ids:
                result = conn.execute(
                    """
                    INSERT OR IGNORE
                    INTO bgm_asset_tags(
                        bgm_id,
                        tag_id
                    )
                    VALUES (?, ?)
                    """,
                    (
                        bgm_id,
                        tag_id,
                    ),
                )
                added += max(
                    0,
                    int(result.rowcount),
                )

    return added


def list_bgm_groups():
    with get_connection() as conn:
        return conn.execute(
            """
            SELECT
                id,
                name,
                parent_group_id,
                sort_order
            FROM bgm_groups
            ORDER BY
                sort_order ASC,
                name COLLATE NOCASE ASC
            """
        ).fetchall()


def create_bgm_group(
    name: str,
    parent_group_id: str | None = None,
) -> str:
    name = str(name or "").strip()

    if not name:
        raise ValueError(
            "グループ名を入力してください。"
        )

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
                """
                SELECT 1
                FROM bgm_groups
                WHERE id = ?
                """,
                (parent_group_id,),
            ).fetchone()

            if parent is None:
                raise ValueError(
                    "親グループが見つかりません。"
                )

        next_order = int(
            conn.execute(
                """
                SELECT COALESCE(MAX(sort_order), -1) + 1
                FROM bgm_groups
                WHERE
                    (
                        parent_group_id = ?
                        OR (
                            parent_group_id IS NULL
                            AND ? IS NULL
                        )
                    )
                """,
                (
                    parent_group_id,
                    parent_group_id,
                ),
            ).fetchone()[0]
        )

        conn.execute(
            """
            INSERT INTO bgm_groups(
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


def rename_bgm_group(
    group_id: str,
    name: str,
) -> None:
    group_id = str(
        group_id or ""
    ).strip()
    name = str(
        name or ""
    ).strip()

    if not name:
        raise ValueError(
            "グループ名を入力してください。"
        )

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE bgm_groups
            SET name = ?
            WHERE id = ?
            """,
            (
                name,
                group_id,
            ),
        )

        if result.rowcount == 0:
            raise ValueError(
                "グループが見つかりません。"
            )


def delete_bgm_group(
    group_id: str,
) -> None:
    group_id = str(
        group_id or ""
    ).strip()

    with get_connection() as conn:
        result = conn.execute(
            """
            DELETE FROM bgm_groups
            WHERE id = ?
            """,
            (group_id,),
        )

        if result.rowcount == 0:
            raise ValueError(
                "グループが見つかりません。"
            )


def add_group_to_bgm(
    bgm_ids,
    group_id: str,
) -> int:
    ids = _clean_ids(bgm_ids)
    group_id = str(
        group_id or ""
    ).strip()

    if not ids or not group_id:
        return 0

    added = 0

    with get_connection() as conn:
        group = conn.execute(
            """
            SELECT 1
            FROM bgm_groups
            WHERE id = ?
            """,
            (group_id,),
        ).fetchone()

        if group is None:
            raise ValueError(
                "グループが見つかりません。"
            )

        for bgm_id in ids:
            exists = conn.execute(
                """
                SELECT 1
                FROM bgm_assets
                WHERE id = ?
                """,
                (bgm_id,),
            ).fetchone()

            if exists is None:
                continue

            result = conn.execute(
                """
                INSERT OR IGNORE
                INTO bgm_asset_groups(
                    bgm_id,
                    group_id
                )
                VALUES (?, ?)
                """,
                (
                    bgm_id,
                    group_id,
                ),
            )

            added += max(
                0,
                int(result.rowcount),
            )

    return added


def set_ccfolia_registration(
    bgm_id: str,
    *,
    media_id: str,
    url: str,
    directory: str = "",
    order: float = 0,
    uploaded: bool = True,
    archived: bool = False,
    ccfolia_updated_at: int | None = None,
    raw=None,
) -> None:
    bgm_id = str(
        bgm_id or ""
    ).strip()
    media_id = str(
        media_id or ""
    ).strip()
    url = str(
        url or ""
    ).strip()

    if not media_id:
        raise ValueError(
            "CCFOLIA media IDが空です。"
        )

    if not url:
        raise ValueError(
            "CCFOLIA URLが空です。"
        )

    raw_json = ""

    if raw is not None:
        raw_json = json.dumps(
            raw,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    with get_connection() as conn:
        result = conn.execute(
            """
            UPDATE bgm_assets
            SET
                ccfolia_media_id = ?,
                ccfolia_url = ?,
                ccfolia_dir = ?,
                ccfolia_order = ?,
                ccfolia_uploaded = ?,
                ccfolia_archived = ?,
                ccfolia_updated_at = ?,
                ccfolia_raw_json = CASE
                    WHEN ? <> ''
                    THEN ?
                    ELSE ccfolia_raw_json
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                media_id,
                url,
                str(directory or ""),
                float(order or 0),
                1 if uploaded else 0,
                1 if archived else 0,
                ccfolia_updated_at,
                raw_json,
                raw_json,
                bgm_id,
            ),
        )

        if result.rowcount == 0:
            raise ValueError(
                "BGMが見つかりません。"
            )


def upsert_salvaged_bgm(
    *,
    media_id: str,
    url: str,
    display_name: str = "",
    content_type: str = "",
    file_size: int = 0,
    directory: str = "",
    order: float = 0,
    volume: float = 0.5,
    loop: bool = True,
    uploaded: bool = True,
    archived: bool = False,
    ccfolia_updated_at: int | None = None,
    raw=None,
) -> tuple[str, bool]:
    media_id = str(
        media_id or ""
    ).strip()
    url = str(
        url or ""
    ).strip()

    if not media_id:
        raise ValueError(
            "CCFOLIA media IDが空です。"
        )

    if not url:
        raise ValueError(
            "CCFOLIA URLが空です。"
        )

    safe_volume = _normalize_volume(
        volume
    )
    directory_text = str(
        directory or ""
    ).strip()
    media_kind = (
        "se"
        if directory_text.lower().startswith("se")
        else "bgm"
    )

    raw_json = (
        json.dumps(
            raw,
            ensure_ascii=False,
            separators=(",", ":"),
        )
        if raw is not None
        else ""
    )

    with get_connection() as conn:
        existing = conn.execute(
            """
            SELECT id
            FROM bgm_assets
            WHERE ccfolia_media_id = ?
            """,
            (media_id,),
        ).fetchone()

        if existing is not None:
            bgm_id = str(
                existing["id"]
            )

            conn.execute(
                """
                UPDATE bgm_assets
                SET
                    display_name = CASE
                        WHEN ? <> '' THEN ?
                        ELSE display_name
                    END,
                    content_type = CASE
                        WHEN ? <> '' THEN ?
                        ELSE content_type
                    END,
                    file_size = CASE
                        WHEN ? > 0 THEN ?
                        ELSE file_size
                    END,
                    default_volume = ?,
                    default_loop = ?,
                    media_kind = ?,
                    ccfolia_url = ?,
                    ccfolia_dir = ?,
                    ccfolia_order = ?,
                    ccfolia_uploaded = ?,
                    ccfolia_archived = ?,
                    ccfolia_updated_at = ?,
                    ccfolia_raw_json = CASE
                        WHEN ? <> ''
                        THEN ?
                        ELSE ccfolia_raw_json
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    str(display_name or "").strip(),
                    str(display_name or "").strip(),
                    str(content_type or "").strip(),
                    str(content_type or "").strip(),
                    max(
                        0,
                        int(file_size or 0),
                    ),
                    max(
                        0,
                        int(file_size or 0),
                    ),
                    safe_volume,
                    1 if loop else 0,
                    media_kind,
                    url,
                    directory_text,
                    float(order or 0),
                    1 if uploaded else 0,
                    1 if archived else 0,
                    ccfolia_updated_at,
                    raw_json,
                    raw_json,
                    bgm_id,
                ),
            )

            return bgm_id, False

        bgm_id = generate_app_id()
        name = (
            str(display_name or "").strip()
            or f"BGM {media_id[:8]}"
        )

        conn.execute(
            """
            INSERT INTO bgm_assets(
                id,
                display_name,
                content_type,
                file_size,
                default_volume,
                default_loop,
                media_kind,
                source,
                ccfolia_media_id,
                ccfolia_url,
                ccfolia_dir,
                ccfolia_order,
                ccfolia_uploaded,
                ccfolia_archived,
                ccfolia_updated_at,
                ccfolia_raw_json
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                'ccfolia_salvage',
                ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                bgm_id,
                name,
                str(content_type or "").strip(),
                max(
                    0,
                    int(file_size or 0),
                ),
                safe_volume,
                1 if loop else 0,
                media_kind,
                media_id,
                url,
                directory_text,
                float(order or 0),
                1 if uploaded else 0,
                1 if archived else 0,
                ccfolia_updated_at,
                raw_json,
            ),
        )

    return bgm_id, True

# BGM_DESKTOP_GROUP_ASSIGN_V1
def set_bgm_groups(
    bgm_id: str,
    group_ids,
) -> None:
    bgm_id = str(bgm_id or "").strip()
    ids = _clean_ids(group_ids)

    with get_connection() as conn:
        exists = conn.execute(
            """
            SELECT 1
            FROM bgm_assets
            WHERE id = ?
            """,
            (bgm_id,),
        ).fetchone()

        if exists is None:
            raise ValueError("BGMが見つかりません。")

        for group_id in ids:
            group = conn.execute(
                """
                SELECT 1
                FROM bgm_groups
                WHERE id = ?
                """,
                (group_id,),
            ).fetchone()

            if group is None:
                raise ValueError("グループが見つかりません。")

        conn.execute(
            """
            DELETE FROM bgm_asset_groups
            WHERE bgm_id = ?
            """,
            (bgm_id,),
        )

        for group_id in ids:
            conn.execute(
                """
                INSERT INTO bgm_asset_groups(
                    bgm_id,
                    group_id
                )
                VALUES (?, ?)
                """,
                (bgm_id, group_id),
            )
