from __future__ import annotations

# CHARACTER_SALVAGE_SERVICE_V1

import json
import math
import mimetypes
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from app.db.database import get_connection
from app.ids import generate_app_id
from app.paths import APP_DATA_DIR, PROJECT_ROOT


CHARACTER_IMAGE_DIR = APP_DATA_DIR / "images"
_ALLOWED_IMAGE_HOSTS = {
    "storage.ccfolia-cdn.net",
    "firebasestorage.googleapis.com",
}
_MAX_IMAGE_BYTES = 25 * 1024 * 1024
_MAX_CHARACTERS_PER_IMPORT = 1000


def _clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _clean_bool(value) -> int:
    return 1 if bool(value) else 0


def _clean_number(value, default=0.0):
    if value is None or value == "":
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if not math.isfinite(number):
        return default
    return number


def _status_number(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return number


def _validate_ccfolia_image_url(value: str) -> str:
    raw = _clean_text(value).strip()
    if not raw:
        raise ValueError("画像URLが空です。")

    parsed = urlparse(raw)
    if parsed.scheme != "https":
        raise ValueError("HTTPS以外の画像URLは使用できません。")

    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_IMAGE_HOSTS:
        raise ValueError("CCFOLIAの画像URLとして扱えないホストです。")

    path_lower = parsed.path.lower()
    if host == "storage.ccfolia-cdn.net":
        if not path_lower.startswith("/users/"):
            raise ValueError("CCFOLIA CDNの想定外パスです。")

    if host == "firebasestorage.googleapis.com":
        expected = "/v0/b/ccfolia-160aa.appspot.com/o/users%2f"
        if not path_lower.startswith(expected):
            raise ValueError("CCFOLIA旧Storageの想定外パスです。")

    return raw


def _image_suffix(content_type: str, source_url: str) -> str:
    content_type = _clean_text(content_type).split(";", 1)[0].strip().lower()
    explicit = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
        "image/bmp": ".bmp",
        "image/avif": ".avif",
    }
    if content_type in explicit:
        return explicit[content_type]

    guessed = mimetypes.guess_extension(content_type) if content_type else None
    if guessed:
        return guessed

    source_suffix = Path(urlparse(source_url).path).suffix.lower()
    if source_suffix in {
        ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".avif"
    }:
        return source_suffix

    return ".img"


def _download_character_image(*, character_id: str, image_url: str) -> tuple[str, str]:
    safe_url = _validate_ccfolia_image_url(image_url)
    request = urllib.request.Request(
        safe_url,
        headers={
            "User-Agent": "CCFOLIA-Manager/1.0",
            "Accept": "image/*",
        },
        method="GET",
    )

    with urllib.request.urlopen(request, timeout=15) as response:
        final_url = _validate_ccfolia_image_url(response.geturl())
        content_type = _clean_text(
            response.headers.get("Content-Type", "")
        ).split(";", 1)[0].strip().lower()

        if content_type and not content_type.startswith("image/"):
            raise ValueError(f"画像ではないContent-Typeです: {content_type}")

        content_length = response.headers.get("Content-Length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                size = 0
            if size > _MAX_IMAGE_BYTES:
                raise ValueError("画像ファイルが大きすぎます。")

        data = response.read(_MAX_IMAGE_BYTES + 1)

    if len(data) > _MAX_IMAGE_BYTES:
        raise ValueError("画像ファイルが大きすぎます。")
    if not data:
        raise ValueError("画像データが空です。")

    image_id = generate_app_id()
    suffix = _image_suffix(content_type, final_url)
    target_dir = CHARACTER_IMAGE_DIR / character_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{image_id}{suffix}"
    target.write_bytes(data)

    relative_path = target.relative_to(PROJECT_ROOT).as_posix()
    return image_id, relative_path


def _source_already_exists(conn, source_character_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1
        FROM characters
        WHERE cocofolia_source_id = ?
          AND deleted_at IS NULL
        LIMIT 1
        """,
        (source_character_id,),
    ).fetchone()
    if row is not None:
        return True

    row = conn.execute(
        """
        SELECT 1
        FROM cocofolia_character_raw
        WHERE source_character_id = ?
        LIMIT 1
        """,
        (source_character_id,),
    ).fetchone()
    return row is not None


# CHARACTER_SALVAGE_ROOM_TAG_SERVICE_V1
def _ensure_room_tag(
    conn,
    room_name: str,
) -> str | None:
    tag_name = _clean_text(room_name).strip()

    if not tag_name:
        return None

    row = conn.execute(
        """
        SELECT id
        FROM tags
        WHERE name = ?
        LIMIT 1
        """,
        (tag_name,),
    ).fetchone()

    if row is not None:
        return str(row["id"])

    tag_id = generate_app_id()

    conn.execute(
        """
        INSERT INTO tags(
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

    return tag_id


def _require_character_raw_table(conn) -> None:
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = 'cocofolia_character_raw'
        """
    ).fetchone()
    if row is None:
        raise RuntimeError(
            "cocofolia_character_raw がありません。"
            " 旧CCMデータ移行後のCharacterスキーマが必要です。"
        )


def _insert_character(
    conn,
    *,
    source_character_id: str,
    room_id: str,
    room_name: str,
    raw: dict,
) -> str:
    character_id = generate_app_id()
    export_id = generate_app_id()

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
            cocofolia_export_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            character_id,
            _clean_text(raw.get("name")),
            _clean_text(raw.get("playerName")),
            _clean_text(raw.get("memo")),
            _clean_number(raw.get("initiative"), 0.0),
            _clean_text(raw.get("externalUrl")),
            _clean_text(raw.get("color")).strip() or "#888888",
            _clean_bool(raw.get("secret")),
            _clean_bool(raw.get("invisible")),
            _clean_bool(raw.get("hideStatus")),
            source_character_id,
            export_id,
        ),
    )

    statuses = raw.get("status")
    if isinstance(statuses, list):
        for index, item in enumerate(statuses):
            if not isinstance(item, dict):
                continue
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
                    _clean_text(item.get("label")),
                    _status_number(item.get("value")),
                    _status_number(item.get("max")),
                    index,
                ),
            )

    params = raw.get("params")
    if isinstance(params, list):
        for index, item in enumerate(params):
            if not isinstance(item, dict):
                continue
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
                    _clean_text(item.get("label")),
                    _clean_text(item.get("value")),
                    index,
                ),
            )

    commands = raw.get("commands")
    if commands not in (None, "", []):
        if isinstance(commands, str):
            content = commands
        else:
            content = json.dumps(commands, ensure_ascii=False, separators=(",", ":"))

        conn.execute(
            """
            INSERT INTO chat_palettes(
                id,
                character_id,
                name,
                mode,
                content,
                sort_order
            )
            VALUES (?, ?, ?, 'normal', ?, 0)
            """,
            (
                generate_app_id(),
                character_id,
                "CCFOLIA",
                content,
            ),
        )

    raw_payload = {
        "room_id": room_id,
        "room_name": room_name,
        "source_character_id": source_character_id,
        "character": raw,
    }
    raw_json = json.dumps(raw_payload, ensure_ascii=False, separators=(",", ":"))

    conn.execute(
        """
        INSERT INTO cocofolia_character_raw(
            character_id,
            source_character_id,
            raw_json,
            source_token
        )
        VALUES (?, ?, ?, '')
        """,
        (
            character_id,
            source_character_id,
            raw_json,
        ),
    )

    return character_id


def import_room_characters(
    *,
    room_id: str,
    room_name: str = "",
    characters,
) -> dict:
    room_id = _clean_text(room_id).strip()
    room_name = _clean_text(room_name).strip()
    if not room_id:
        raise ValueError("room_id がありません。")
    if not isinstance(characters, list):
        raise ValueError("characters は配列で指定してください。")
    if len(characters) > _MAX_CHARACTERS_PER_IMPORT:
        raise ValueError(
            f"一度に取り込めるキャラクターは{_MAX_CHARACTERS_PER_IMPORT}件までです。"
        )

    imported = 0
    skipped = 0
    image_imported = 0
    image_failed = 0
    image_errors = []
    imported_ids = []
    pending_images = []

    with get_connection() as conn:
        _require_character_raw_table(conn)

        for entry in characters:
            if not isinstance(entry, dict):
                skipped += 1
                continue

            source_character_id = _clean_text(entry.get("id")).strip()
            raw = entry.get("fields")

            if not source_character_id or not isinstance(raw, dict):
                skipped += 1
                continue

            if _source_already_exists(conn, source_character_id):
                skipped += 1
                continue

            character_id = _insert_character(
                conn,
                source_character_id=source_character_id,
                room_id=room_id,
                room_name=room_name,
                raw=raw,
            )
            imported += 1
            imported_ids.append(character_id)

            icon_url = _clean_text(raw.get("iconUrl")).strip()
            if icon_url:
                pending_images.append((character_id, source_character_id, icon_url))

        tagged = 0
        room_tag = ""

        if imported_ids and room_name:
            tag_id = _ensure_room_tag(
                conn,
                room_name,
            )

            if tag_id is not None:
                conn.executemany(
                    """
                    INSERT OR IGNORE INTO character_tags(
                        character_id,
                        tag_id
                    )
                    VALUES (?, ?)
                    """,
                    [
                        (
                            character_id,
                            tag_id,
                        )
                        for character_id
                        in imported_ids
                    ],
                )

                tagged = len(imported_ids)
                room_tag = room_name

    for character_id, source_character_id, icon_url in pending_images:
        try:
            image_id, relative_path = _download_character_image(
                character_id=character_id,
                image_url=icon_url,
            )
            with get_connection() as conn:
                conn.execute(
                    """
                    INSERT INTO character_images(
                        id,
                        character_id,
                        relative_path,
                        label,
                        sort_order
                    )
                    VALUES (?, ?, ?, ?, 0)
                    """,
                    (
                        image_id,
                        character_id,
                        relative_path,
                        "CCFOLIA",
                    ),
                )
            image_imported += 1
        except Exception as exc:
            image_failed += 1
            image_errors.append(
                {
                    "source_character_id": source_character_id,
                    "error": str(exc),
                }
            )

    return {
        "received": len(characters),
        "imported": imported,
        "skipped": skipped,
        "image_imported": image_imported,
        "image_failed": image_failed,
        "image_errors": image_errors[:20],
        "character_ids": imported_ids,
        "room_tag": room_tag,
        "tagged": tagged,
    }
