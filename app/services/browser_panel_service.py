from __future__ import annotations

from app.db.database import get_connection
from app.services.character_lifecycle_service import (
    duplicate_character,
    soft_delete_character,
)
from app.services.character_service import (
    add_group_to_characters,
    add_tags_to_characters,
    create_character,
    create_group,
    delete_group,
    get_character_bundle,
    list_groups,
    list_tags,
    rename_group,
)
from app.services.v22_character_service import apply_template_v22


QUICK_MEMO_COLUMN = "quick_memo"


def ensure_browser_panel_schema():
    with get_connection() as conn:
        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(characters)"
            ).fetchall()
        }

        if QUICK_MEMO_COLUMN not in columns:
            conn.execute(
                """
                ALTER TABLE characters
                ADD COLUMN quick_memo TEXT NOT NULL DEFAULT ''
                """
            )


def _active_character(conn, character_id: str):
    return conn.execute(
        """
        SELECT *
        FROM characters
        WHERE id = ?
          AND deleted_at IS NULL
        """,
        (character_id,),
    ).fetchone()


def get_character_panel_detail(character_id: str):
    ensure_browser_panel_schema()

    bundle = get_character_bundle(character_id)
    character = dict(bundle["character"])

    with get_connection() as conn:
        row = _active_character(
            conn,
            character_id,
        )

        if row is None:
            raise ValueError(
                "キャラクターが見つかりません。"
            )

        quick_memo = str(
            row[QUICK_MEMO_COLUMN]
            or ""
        )

    return {
        "id": str(character["id"]),
        "name": str(character.get("name") or ""),
        "player_name": str(
            character.get("player_name")
            or ""
        ),
        "color": str(
            character.get("color")
            or "#888888"
        ),
        "template_id": str(
            character.get("template_id")
            or ""
        ),
        "quick_memo": quick_memo,
        "tags": [
            {
                "id": str(row["id"]),
                "name": str(row["name"]),
            }
            for row in bundle["tags"]
        ],
        "group_ids": [
            str(value)
            for value in bundle["group_ids"]
        ],
    }


def set_quick_memo(
    character_id: str,
    text: str,
):
    ensure_browser_panel_schema()
    text = str(text or "")

    if len(text) > 200_000:
        raise ValueError(
            "Quick Memo が長すぎます。"
        )

    with get_connection() as conn:
        row = _active_character(
            conn,
            character_id,
        )

        if row is None:
            raise ValueError(
                "キャラクターが見つかりません。"
            )

        conn.execute(
            """
            UPDATE characters
            SET quick_memo = ?
            WHERE id = ?
            """,
            (
                text,
                character_id,
            ),
        )


def create_browser_character(
    name: str,
    template_id: str = "generic",
):
    name = str(name or "").strip()

    if not name:
        raise ValueError(
            "キャラクター名を入力してください。"
        )

    template_id = str(
        template_id
        or "generic"
    ).strip().lower()

    if template_id not in {
        "generic",
        "coc6",
    }:
        raise ValueError(
            "未対応のテンプレートです。"
        )

    character_id = create_character(
        name
    )

    try:
        if template_id == "coc6":
            apply_template_v22(
                character_id,
                "coc6",
            )
        else:
            apply_template_v22(
                character_id,
                "generic",
            )
    except Exception:
        soft_delete_character(
            character_id
        )
        raise

    return character_id


def duplicate_browser_character(
    character_id: str,
):
    return duplicate_character(
        character_id
    )


def trash_browser_character(
    character_id: str,
):
    soft_delete_character(
        character_id
    )


def add_browser_tags(
    character_id: str,
    tag_names,
):
    return add_tags_to_characters(
        [character_id],
        list(tag_names or []),
    )


def add_browser_group(
    character_id: str,
    group_id: str,
):
    return add_group_to_characters(
        [character_id],
        group_id,
    )


def browser_tags():
    return [
        {
            "id": str(row["id"]),
            "name": str(row["name"]),
        }
        for row in list_tags()
    ]


def browser_groups():
    return [
        {
            "id": str(row["id"]),
            "name": str(row["name"]),
            "parent_group_id": (
                None
                if row["parent_group_id"] is None
                else str(row["parent_group_id"])
            ),
            "sort_order": int(
                row["sort_order"]
                or 0
            ),
        }
        for row in list_groups()
    ]


def create_browser_group(
    name: str,
    parent_group_id=None,
):
    parent_group_id = (
        None
        if parent_group_id in (
            None,
            "",
        )
        else str(parent_group_id)
    )

    return create_group(
        str(name or ""),
        parent_group_id,
    )


def rename_browser_group(
    group_id: str,
    name: str,
):
    rename_group(
        str(group_id),
        str(name or ""),
    )


def delete_browser_group(
    group_id: str,
):
    delete_group(
        str(group_id)
    )

# ---------------------------------------------------------------------------
# Phase 28: browser full editor
# ---------------------------------------------------------------------------

from app.services.advanced_service import load_advanced_bundle
from app.services.v22_character_service import (
    load_v22_bundle,
    save_skills_and_palettes,
    save_v22_bundle,
)

def _text(value) -> str:
    return "" if value is None else str(value)


def _bool(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
    return bool(value)


def _list(value, field_name: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(
            f"{field_name} は配列で指定してください。"
        )
    return value


def get_character_editor_bundle(character_id: str) -> dict:
    ensure_browser_panel_schema()

    bundle = load_v22_bundle(character_id)
    advanced = load_advanced_bundle(character_id)
    character = dict(bundle["character"])

    statuses = []
    for row in bundle["statuses"]:
        row = dict(row)
        statuses.append(
            {
                "label": _text(row.get("label")),
                "current": _text(row.get("current_value")),
                "max": _text(row.get("max_value")),
                "initial_formula": _text(
                    row.get("initial_formula")
                ),
                "max_formula": _text(
                    row.get("max_formula")
                ),
                "formula_error": _text(
                    row.get("formula_error")
                ),
            }
        )

    params = []
    for row in bundle["params"]:
        row = dict(row)
        params.append(
            {
                "label": _text(row.get("label")),
                "value": _text(row.get("value")),
                "formula": _text(row.get("formula")),
                "formula_error": _text(
                    row.get("formula_error")
                ),
            }
        )

    memos = []
    for row in bundle["memos"]:
        row = dict(row)
        memos.append(
            {
                "title": _text(row.get("title")),
                "body": _text(row.get("body")),
                "private": bool(row.get("is_private")),
            }
        )

    skills = []
    for row in advanced["skills"]:
        row = dict(row)
        skills.append(
            {
                "label": _text(row.get("label")),
                "value": _text(row.get("value")),
                "category": _text(row.get("category")),
            }
        )

    palettes = []
    for row in advanced["palettes"]:
        row = dict(row)
        palettes.append(
            {
                "name": _text(row.get("name")),
                "mode": _text(row.get("mode")) or "normal",
                "content": _text(row.get("content")),
            }
        )

    return {
        "character": {
            "id": _text(character.get("id")),
            "name": _text(character.get("name")),
            "player_name": _text(character.get("player_name")),
            "initiative": _text(character.get("initiative")),
            "external_url": _text(character.get("external_url")),
            "color": _text(character.get("color")) or "#888888",
            "secret": bool(character.get("secret")),
            "invisible": bool(character.get("invisible")),
            "hide_status": bool(character.get("hide_status")),
            "template_id": _text(character.get("template_id")),
            "image_count": len(bundle["images"]),
        },
        "statuses": statuses,
        "params": params,
        "skills": skills,
        "memos": memos,
        "palettes": palettes,
        "tags": [
            _text(row["name"])
            for row in bundle["tags"]
        ],
        "group_ids": [
            _text(value)
            for value in bundle["group_ids"]
        ],
        "groups": browser_groups(),
    }


def save_character_editor_bundle(
    character_id: str,
    payload: dict,
) -> dict:
    if not isinstance(payload, dict):
        raise ValueError(
            "保存データの形式が不正です。"
        )

    current = get_character_bundle(character_id)
    character_current = dict(current["character"])

    character_data = payload.get("character") or {}
    if not isinstance(character_data, dict):
        raise ValueError(
            "基本情報の形式が不正です。"
        )

    statuses = _list(
        payload.get("statuses"),
        "statuses",
    )
    params = _list(
        payload.get("params"),
        "params",
    )
    skills = _list(
        payload.get("skills"),
        "skills",
    )
    memos = _list(
        payload.get("memos"),
        "memos",
    )
    palettes = _list(
        payload.get("palettes"),
        "palettes",
    )
    tags = _list(
        payload.get("tags"),
        "tags",
    )
    group_ids = _list(
        payload.get("group_ids"),
        "group_ids",
    )

    clean_character = {
        "name": _text(
            character_data.get(
                "name",
                character_current.get("name"),
            )
        ),
        "player_name": _text(
            character_data.get(
                "player_name",
                character_current.get("player_name"),
            )
        ),
        "initiative": _text(
            character_data.get(
                "initiative",
                character_current.get("initiative", 0),
            )
        ),
        "external_url": _text(
            character_data.get(
                "external_url",
                character_current.get("external_url"),
            )
        ),
        "color": _text(
            character_data.get(
                "color",
                character_current.get("color") or "#888888",
            )
        ) or "#888888",
        "secret": _bool(
            character_data.get(
                "secret",
                character_current.get("secret"),
            )
        ),
        "invisible": _bool(
            character_data.get(
                "invisible",
                character_current.get("invisible"),
            )
        ),
        "hide_status": _bool(
            character_data.get(
                "hide_status",
                character_current.get("hide_status"),
            )
        ),
    }

    clean_statuses = []
    for row in statuses:
        if not isinstance(row, dict):
            raise ValueError(
                "ステータス行の形式が不正です。"
            )
        clean_statuses.append(
            {
                "label": _text(row.get("label")),
                "current": _text(row.get("current")),
                "max": _text(row.get("max")),
                "initial_formula": _text(
                    row.get("initial_formula")
                ),
                "max_formula": _text(
                    row.get("max_formula")
                ),
            }
        )

    clean_params = []
    for row in params:
        if not isinstance(row, dict):
            raise ValueError(
                "パラメータ行の形式が不正です。"
            )
        clean_params.append(
            {
                "label": _text(row.get("label")),
                "value": _text(row.get("value")),
                "formula": _text(row.get("formula")),
            }
        )

    clean_skills = []
    for row in skills:
        if not isinstance(row, dict):
            raise ValueError(
                "技能行の形式が不正です。"
            )
        clean_skills.append(
            {
                "label": _text(row.get("label")),
                "value": _text(row.get("value")),
                "category": _text(row.get("category")),
            }
        )

    clean_memos = []
    for row in memos:
        if not isinstance(row, dict):
            raise ValueError(
                "メモ行の形式が不正です。"
            )
        clean_memos.append(
            {
                "title": _text(row.get("title")),
                "body": _text(row.get("body")),
                "private": _bool(row.get("private")),
            }
        )

    clean_palettes = []
    for row in palettes:
        if not isinstance(row, dict):
            raise ValueError(
                "チャットパレット行の形式が不正です。"
            )
        mode = _text(row.get("mode")) or "normal"
        if mode not in {"normal", "kp"}:
            mode = "normal"
        clean_palettes.append(
            {
                "name": _text(row.get("name")),
                "mode": mode,
                "content": _text(row.get("content")),
            }
        )

    clean_tags = [
        _text(value).strip()
        for value in tags
        if _text(value).strip()
    ]
    clean_group_ids = [
        _text(value).strip()
        for value in group_ids
        if _text(value).strip()
    ]

    template_id = _text(
        character_current.get("template_id")
    )

    save_v22_bundle(
        character_id,
        clean_character,
        current["images"],
        clean_statuses,
        clean_params,
        clean_memos,
        clean_tags,
        clean_group_ids,
        template_id,
    )

    save_skills_and_palettes(
        character_id,
        clean_skills,
        clean_palettes,
    )

    return get_character_editor_bundle(
        character_id
    )

# ---------------------------------------------------------------------------
# Phase 29: browser icon helper
# ---------------------------------------------------------------------------

import base64
import mimetypes

from app.paths import PROJECT_ROOT


def get_character_icon_data_url(character_id: str):
    bundle = get_character_bundle(character_id)

    for row in bundle["images"]:
        row = dict(row)
        relative_path = str(
            row.get("relative_path")
            or ""
        ).strip()

        if not relative_path:
            continue

        image_path = PROJECT_ROOT / relative_path

        if (
            not image_path.exists()
            or not image_path.is_file()
        ):
            continue

        mime_type = (
            mimetypes.guess_type(
                image_path.name
            )[0]
            or "application/octet-stream"
        )

        data = base64.b64encode(
            image_path.read_bytes()
        ).decode("ascii")

        return f"data:{mime_type};base64,{data}"

    return None

# ---------------------------------------------------------------------------
# Phase 30: browser image manager
# ---------------------------------------------------------------------------

import base64
from pathlib import Path

from app.ids import generate_app_id
from app.paths import IMAGES_DIR, PROJECT_ROOT


_BROWSER_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
}

_BROWSER_IMAGE_MAX_BYTES = 12 * 1024 * 1024


def list_browser_character_images(character_id: str) -> list[dict]:
    bundle = get_character_bundle(character_id)
    output = []

    for index, row in enumerate(bundle["images"]):
        row = dict(row)
        output.append(
            {
                "id": str(row["id"]),
                "label": str(row.get("label") or ""),
                "sort_order": index,
                "is_main": index == 0,
            }
        )

    return output


def get_browser_character_image_data_url(
    character_id: str,
    image_id: str,
):
    bundle = get_character_bundle(character_id)
    target = None

    for raw in bundle["images"]:
        row = dict(raw)
        if str(row["id"]) == str(image_id):
            target = row
            break

    if target is None:
        raise ValueError("画像が見つかりません。")

    relative_path = str(target.get("relative_path") or "").strip()
    if not relative_path:
        return None

    image_path = PROJECT_ROOT / relative_path
    if not image_path.exists() or not image_path.is_file():
        return None

    suffix = image_path.suffix.lower()
    mime_map = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    mime_type = mime_map.get(suffix, "application/octet-stream")
    data = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


def add_browser_character_image(
    character_id: str,
    filename: str,
    data_base64: str,
) -> dict:
    filename = Path(str(filename or "")).name
    suffix = Path(filename).suffix.lower()

    if suffix not in _BROWSER_IMAGE_EXTENSIONS:
        raise ValueError("対応していない画像形式です。")

    try:
        raw = base64.b64decode(str(data_base64 or ""), validate=True)
    except Exception as exc:
        raise ValueError("画像データを読み込めません。") from exc

    if not raw:
        raise ValueError("画像データが空です。")
    if len(raw) > _BROWSER_IMAGE_MAX_BYTES:
        raise ValueError("画像は1枚12MB以下にしてください。")

    with get_connection() as conn:
        character = _active_character(conn, character_id)
        if character is None:
            raise ValueError("キャラクターが見つかりません。")

        row = conn.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) AS max_order
            FROM character_images
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()
        sort_order = int(row["max_order"]) + 1

        image_id = generate_app_id()
        target_dir = IMAGES_DIR / character_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / f"{image_id}{suffix}"
        target.write_bytes(raw)
        relative_path = target.relative_to(PROJECT_ROOT).as_posix()

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
                character_id,
                relative_path,
                filename,
                sort_order,
            ),
        )

    return {
        "id": image_id,
        "label": filename,
        "sort_order": sort_order,
        "is_main": sort_order == 0,
    }


def reorder_browser_character_images(
    character_id: str,
    image_ids: list[str],
) -> None:
    image_ids = [
        str(value).strip()
        for value in image_ids
        if str(value).strip()
    ]

    if len(image_ids) != len(set(image_ids)):
        raise ValueError("画像順序に重複があります。")

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM character_images
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()
        existing = {str(row["id"]) for row in rows}

        if set(image_ids) != existing:
            raise ValueError("画像一覧が現在のデータと一致しません。")

        for index, image_id in enumerate(image_ids):
            conn.execute(
                """
                UPDATE character_images
                SET sort_order = ?
                WHERE character_id = ?
                  AND id = ?
                """,
                (index, character_id, image_id),
            )


def delete_browser_character_image(
    character_id: str,
    image_id: str,
) -> None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT id
            FROM character_images
            WHERE character_id = ?
              AND id = ?
            """,
            (character_id, image_id),
        ).fetchone()

        if row is None:
            raise ValueError("画像が見つかりません。")

        conn.execute(
            """
            DELETE FROM character_images
            WHERE character_id = ?
              AND id = ?
            """,
            (character_id, image_id),
        )

        rows = conn.execute(
            """
            SELECT id
            FROM character_images
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        for index, row in enumerate(rows):
            conn.execute(
                """
                UPDATE character_images
                SET sort_order = ?
                WHERE id = ?
                """,
                (index, row["id"]),
            )
