from __future__ import annotations

# IMAGES_BROWSER_SERVICE_V1

import base64
import binascii
import hashlib
import tempfile
import urllib.request
from urllib.parse import urlparse
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, Qt
from PySide6.QtGui import QImageReader

from app.db.database import get_connection
from app.paths import APP_DATA_DIR, IMAGE_ASSETS_DIR, PROJECT_ROOT
from app.services.image_service import (
    get_image_asset,
    import_image_asset,
    list_image_assets,
    list_image_groups,
    list_image_tags,
    set_ccfolia_registration,
    upsert_salvaged_image,
)


def _safe_local_asset_path(relative_path: str) -> Path | None:
    relative = str(relative_path or "").strip()
    if not relative:
        return None

    try:
        path = (PROJECT_ROOT / relative).resolve()
        root = IMAGE_ASSETS_DIR.resolve()

        if not path.is_relative_to(root):
            return None

        if not path.is_file():
            return None

        return path
    except Exception:
        return None


def _serialize_asset(row) -> dict:
    return {
        "id": str(row["id"]),
        "display_name": str(row["display_name"] or ""),
        "original_filename": str(row["original_filename"] or ""),
        "content_type": str(row["content_type"] or ""),
        "file_size": int(row["file_size"] or 0),
        "ccfolia_registered": bool(row["ccfolia_registered"]),
        "has_local": bool(str(row["local_path"] or "").strip()),
    }


# IMAGES_BROWSER_PAGINATION_SERVICE
def list_browser_image_assets(
    *,
    search_text: str = "",
    search_mode: str = "keyword",
    group_id: str | None = None,
    only_ungrouped: bool = False,
    only_untagged: bool = False,
    limit: int = 120,
    offset: int = 0,
) -> dict:
    limit = max(1, min(int(limit or 120), 240))
    offset = max(0, int(offset or 0))

    rows = list_image_assets(
        search_text=search_text,
        search_mode=search_mode,
        group_id=group_id,
        only_ungrouped=only_ungrouped,
        only_untagged=only_untagged,
        limit=limit,
        offset=offset,
    )

    total = (
        int(rows[0]["total_count"] or 0)
        if rows
        else 0
    )

    return {
        "assets": [
            _serialize_asset(row)
            for row in rows
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }



def get_browser_image_apply_info(image_id: str) -> dict:
    row = get_image_asset(image_id)

    if row is None:
        raise ValueError("画像が見つかりません。")

    url = str(row["ccfolia_url"] or "").strip()

    return {
        "id": str(row["id"]),
        "display_name": str(
            row["display_name"]
            or row["original_filename"]
            or "画像"
        ),
        "ccfolia_registered": bool(url),
        "url": url,
    }


# IM6_IMAGE_UPLOAD_SERVICE
def get_browser_image_upload_source(image_id: str) -> dict:
    row = get_image_asset(image_id)

    if row is None:
        raise ValueError("画像が見つかりません。")

    local_path = _safe_local_asset_path(
        str(row["local_path"] or "")
    )

    if local_path is None:
        raise ValueError(
            "ローカル画像本体が見つかりません。"
        )

    raw = local_path.read_bytes()

    filename = str(
        row["original_filename"]
        or local_path.name
        or f"{row['id']}.png"
    )

    content_type = str(
        row["content_type"]
        or ""
    ).strip()

    if not content_type.startswith("image/"):
        content_type = "image/png"

    return {
        "id": str(row["id"]),
        "display_name": str(
            row["display_name"]
            or row["original_filename"]
            or "画像"
        ),
        "filename": filename,
        "content_type": content_type,
        "file_size": len(raw),
        "data_base64": base64.b64encode(
            raw
        ).decode("ascii"),
    }


def register_browser_image_ccfolia(
    *,
    image_id: str,
    file_id: str,
    url: str,
    content_type: str = "",
    file_size: int | None = None,
) -> dict:
    set_ccfolia_registration(
        image_id,
        file_id=file_id,
        url=url,
        content_type=content_type,
        file_size=file_size,
    )

    row = get_image_asset(image_id)

    if row is None:
        raise ValueError("画像が見つかりません。")

    return {
        "id": str(row["id"]),
        "ccfolia_file_id": str(
            row["ccfolia_file_id"] or ""
        ),
        "ccfolia_url": str(
            row["ccfolia_url"] or ""
        ),
        "ccfolia_registered": bool(
            str(row["ccfolia_url"] or "").strip()
        ),
    }


def import_browser_image(
    *,
    filename: str,
    data_base64: str,
) -> dict:
    filename = Path(
        str(filename or "image.png")
    ).name

    if not filename:
        filename = "image.png"

    payload = str(data_base64 or "").strip()

    if not payload:
        raise ValueError(
            "画像データが空です。"
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
            "画像データが不正です。"
        ) from exc

    if not raw:
        raise ValueError(
            "画像データが空です。"
        )

    suffix = Path(filename).suffix.lower()

    if suffix not in {
        ".png",
        ".jpg",
        ".jpeg",
        ".jfif",
        ".webp",
        ".gif",
        ".bmp",
        ".avif",
    }:
        raise ValueError(
            "対応していない画像形式です。"
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
            prefix="image_import_",
            dir=APP_DATA_DIR,
            delete=False,
        ) as handle:
            handle.write(raw)
            temporary_path = Path(
                handle.name
            )

        image_id = import_image_asset(
            temporary_path,
            display_name=Path(
                filename
            ).stem,
            source="browser_import",
        )

    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(
                    missing_ok=True
                )
            except OSError:
                pass

    row = get_image_asset(image_id)

    return {
        "id": str(image_id),
        "display_name": str(
            row["display_name"]
            if row is not None
            else Path(filename).stem
        ),
        "filename": filename,
    }

def browser_image_tags() -> list[dict]:
    return [
        {
            "id": str(row["id"]),
            "name": str(row["name"] or ""),
        }
        for row in list_image_tags()
    ]


def browser_image_groups() -> list[dict]:
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
        for row in list_image_groups()
    ]


@lru_cache(maxsize=512)
def _local_preview_data_url(
    path_text: str,
    modified_ns: int,
    max_width: int,
    max_height: int,
) -> str:
    del modified_ns

    path = Path(path_text)

    reader = QImageReader(str(path))
    reader.setAutoTransform(True)

    image = reader.read()
    if image.isNull():
        return ""

    if (
        image.width() > max_width
        or image.height() > max_height
    ):
        image = image.scaled(
            max_width,
            max_height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation,
        )

    has_alpha = image.hasAlphaChannel()
    fmt = "PNG" if has_alpha else "JPG"
    mime = "image/png" if has_alpha else "image/jpeg"
    quality = -1 if has_alpha else 84

    data = QByteArray()
    buffer = QBuffer(data)

    if not buffer.open(QIODevice.WriteOnly):
        return ""

    try:
        if not image.save(buffer, fmt, quality):
            return ""
    finally:
        buffer.close()

    encoded = base64.b64encode(
        bytes(data)
    ).decode("ascii")

    return f"data:{mime};base64,{encoded}"


def get_browser_image_preview(
    image_id: str,
    *,
    size: str = "thumb",
) -> dict:
    row = get_image_asset(image_id)

    if row is None:
        raise ValueError("画像が見つかりません。")

    remote_url = str(row["ccfolia_url"] or "").strip()
    local_path = _safe_local_asset_path(
        str(row["local_path"] or "")
    )

    size_key = str(size or "thumb").strip().lower()

    if size_key == "large":
        max_width = 960
        max_height = 720
    else:
        size_key = "thumb"
        max_width = 300
        max_height = 210

    if local_path is not None:
        try:
            modified_ns = local_path.stat().st_mtime_ns
            source = _local_preview_data_url(
                str(local_path),
                modified_ns,
                max_width,
                max_height,
            )
        except OSError:
            source = ""

        if source:
            return {
                "src": source,
                "source": "local",
                "size": size_key,
            }

    if remote_url:
        return {
            "src": remote_url,
            "source": "ccfolia",
            "size": size_key,
        }

    return {
        "src": "",
        "source": "missing",
        "size": size_key,
    }


# IM7_IMAGE_SALVAGE_SERVICE
_SALVAGE_EXTENSIONS = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/bmp": ".bmp",
    "image/avif": ".avif",
}


# IM7_BACKGROUND_ONLY_SALVAGE_SERVICE
def _validate_ccfolia_image_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())

    if parsed.scheme != "https":
        raise ValueError(
            "CCFOLIA画像URLとして扱えないURLです。"
        )

    host = str(parsed.hostname or "").lower()
    path_lower = str(parsed.path or "").lower()

    if host == "storage.ccfolia-cdn.net":
        if not path_lower.startswith("/users/"):
            raise ValueError(
                "CCFOLIA CDNの画像パスとして扱えません。"
            )
        return parsed.geturl()

    # Older CCFOLIA uploads can still point at the legacy Firebase Storage URL.
    if host == "firebasestorage.googleapis.com":
        legacy_prefix = (
            "/v0/b/ccfolia-160aa.appspot.com/o/users%2f"
        )
        if not path_lower.startswith(legacy_prefix):
            raise ValueError(
                "CCFOLIA旧Firebase Storageの画像パスとして扱えません。"
            )
        return parsed.geturl()

    raise ValueError(
        "CCFOLIA画像URLとして扱えないホストです。"
    )


def _download_ccfolia_image_bytes(
    url: str,
    *,
    max_bytes: int = 32 * 1024 * 1024,
) -> bytes:
    safe_url = _validate_ccfolia_image_url(url)
    request = urllib.request.Request(
        safe_url,
        headers={
            "User-Agent": "CCFOLIA-Manager/0.7",
            "Accept": "image/*,*/*;q=0.8",
        },
        method="GET",
    )

    with urllib.request.urlopen(
        request,
        timeout=20,
    ) as response:
        raw = response.read(max_bytes + 1)

    if not raw:
        raise ValueError(
            "CCFOLIA画像データが空です。"
        )

    if len(raw) > max_bytes:
        raise ValueError(
            "CCFOLIA画像が32MBを超えています。"
        )

    return raw


def _local_asset_sha256(
    relative_path: str,
) -> str | None:
    path = _safe_local_asset_path(relative_path)
    if path is None:
        return None

    digest = hashlib.sha256()

    try:
        with path.open("rb") as handle:
            for chunk in iter(
                lambda: handle.read(1024 * 1024),
                b"",
            ):
                digest.update(chunk)
    except OSError:
        return None

    return digest.hexdigest()


def _find_unique_local_match(
    raw: bytes,
) -> str | None:
    file_size = len(raw)
    remote_hash = hashlib.sha256(raw).hexdigest()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, local_path
            FROM image_assets
            WHERE file_size = ?
              AND COALESCE(local_path, '') <> ''
              AND COALESCE(ccfolia_file_id, '') = ''
            """,
            (file_size,),
        ).fetchall()

    matches = []

    for row in rows:
        local_hash = _local_asset_sha256(
            str(row["local_path"] or "")
        )

        if local_hash == remote_hash:
            matches.append(str(row["id"]))

            if len(matches) > 1:
                return None

    return matches[0] if matches else None


def _persist_salvaged_bytes(
    image_id: str,
    *,
    raw: bytes,
    file_id: str,
    content_type: str,
) -> None:
    safe_content_type = str(
        content_type or ""
    ).strip().lower()

    suffix = _SALVAGE_EXTENSIONS.get(
        safe_content_type,
        ".img",
    )

    target_dir = IMAGE_ASSETS_DIR / image_id
    target_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    target = target_dir / f"source{suffix}"
    temporary = target_dir / f".source{suffix}.tmp"
    temporary.write_bytes(raw)
    temporary.replace(target)

    for other in target_dir.glob("source.*"):
        if other == target:
            continue
        try:
            other.unlink()
        except OSError:
            pass

    relative_path = target.relative_to(
        PROJECT_ROOT
    ).as_posix()

    original_filename = (
        f"ccfolia_{file_id[:12]}{suffix}"
    )

    with get_connection() as conn:
        conn.execute(
            """
            UPDATE image_assets
            SET
                local_path = ?,
                original_filename = CASE
                    WHEN COALESCE(original_filename, '') = ''
                    THEN ?
                    ELSE original_filename
                END,
                content_type = CASE
                    WHEN ? <> '' THEN ?
                    ELSE content_type
                END,
                file_size = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                relative_path,
                original_filename,
                safe_content_type,
                safe_content_type,
                len(raw),
                image_id,
            ),
        )


def salvage_browser_images(
    images,
) -> dict:
    if not isinstance(images, list):
        raise ValueError(
            "画像一覧の形式が不正です。"
        )

    if len(images) > 10000:
        raise ValueError(
            "一度に取り込める画像数を超えています。"
        )

    result = {
        "received": len(images),
        "created": 0,
        "linked": 0,
        "updated": 0,
        "remote_only": 0,
        "skipped": 0,
        "errors": [],
    }

    for index, item in enumerate(images, start=1):
        if not isinstance(item, dict):
            result["skipped"] += 1
            continue

        file_id = str(
            item.get("file_id", "")
        ).strip()
        url = str(
            item.get("url", "")
        ).strip()
        content_type = str(
            item.get("content_type", "")
        ).strip().lower()
        display_name = str(
            item.get("display_name", "")
        ).strip()
        directory = str(
            item.get("dir", "")
        ).strip().lower()

        try:
            file_size = max(
                0,
                int(item.get("file_size", 0) or 0),
            )
        except (TypeError, ValueError):
            file_size = 0

        if (
            not file_id
            or not url
            or directory != "background"
            or not content_type.startswith("image/")
        ):
            result["skipped"] += 1
            continue

        try:
            url = _validate_ccfolia_image_url(url)

            with get_connection() as conn:
                existing = conn.execute(
                    """
                    SELECT id, local_path
                    FROM image_assets
                    WHERE ccfolia_file_id = ?
                    """,
                    (file_id,),
                ).fetchone()

            if existing is not None:
                image_id = str(existing["id"])

                set_ccfolia_registration(
                    image_id,
                    file_id=file_id,
                    url=url,
                    content_type=content_type,
                    file_size=(
                        file_size
                        if file_size > 0
                        else None
                    ),
                )

                if not str(
                    existing["local_path"] or ""
                ).strip():
                    try:
                        raw = _download_ccfolia_image_bytes(
                            url
                        )
                        _persist_salvaged_bytes(
                            image_id,
                            raw=raw,
                            file_id=file_id,
                            content_type=content_type,
                        )
                    except Exception:
                        pass

                result["updated"] += 1
                continue

            raw = None

            try:
                raw = _download_ccfolia_image_bytes(
                    url
                )
            except Exception:
                raw = None

            if raw is not None:
                matched_id = _find_unique_local_match(
                    raw
                )

                if matched_id:
                    set_ccfolia_registration(
                        matched_id,
                        file_id=file_id,
                        url=url,
                        content_type=content_type,
                        file_size=len(raw),
                    )
                    result["linked"] += 1
                    continue

            image_id, created = upsert_salvaged_image(
                file_id=file_id,
                url=url,
                content_type=content_type,
                file_size=(
                    len(raw)
                    if raw is not None
                    else file_size
                ),
                display_name=(
                    display_name
                    or f"画像 {file_id[:8]}"
                ),
            )

            if raw is not None:
                _persist_salvaged_bytes(
                    image_id,
                    raw=raw,
                    file_id=file_id,
                    content_type=content_type,
                )

            if created:
                if raw is None:
                    result["remote_only"] += 1
                else:
                    result["created"] += 1
            else:
                result["updated"] += 1

        except Exception as exc:
            result["skipped"] += 1

            if len(result["errors"]) < 20:
                result["errors"].append(
                    {
                        "index": index,
                        "file_id": file_id,
                        "error": str(exc),
                    }
                )

    return result
