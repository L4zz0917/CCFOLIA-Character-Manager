from __future__ import annotations

import copy
import hashlib
import json
import mimetypes
import secrets
import zipfile
from datetime import datetime
from pathlib import Path

from app.db.database import get_connection
from app.ids import generate_app_id, generate_unique_cocofolia_id
from app.paths import EXPORTS_DIR, IMAGES_DIR, PROJECT_ROOT
from app.services.advanced_service import apply_coc6_template
from app.services.formula_engine import FormulaError, evaluate_formula


DATA_FILENAME = "__data.json"
TOKEN_FILENAME = ".token"
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def _ensure_raw_table(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cocofolia_character_raw (
            character_id TEXT PRIMARY KEY,
            source_character_id TEXT NOT NULL DEFAULT '',
            raw_json TEXT NOT NULL DEFAULT '{}',
            source_token TEXT NOT NULL DEFAULT '',
            imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(character_id)
                REFERENCES characters(id)
                ON DELETE CASCADE
        )
        """
    )


def _new_token():
    return "0." + hashlib.sha256(secrets.token_bytes(32)).hexdigest()


def _finite_number(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default

    if number != number or number in (float("inf"), float("-inf")):
        return default

    return number


def _json_number(value, default=0):
    number = _finite_number(value, default)

    if float(number).is_integer():
        return int(number)

    return float(number)


def _mime_for_path(path: Path):
    mime, _ = mimetypes.guess_type(path.name)

    if mime:
        return mime

    suffix = path.suffix.lower()

    if suffix == ".png":
        return "image/png"
    if suffix in (".jpg", ".jpeg"):
        return "image/jpeg"
    if suffix == ".webp":
        return "image/webp"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".bmp":
        return "image/bmp"

    return "application/octet-stream"


def _resource_extension(path: Path):
    suffix = path.suffix.lower()

    if suffix == ".jpg":
        return ".jpeg"

    if suffix in IMAGE_SUFFIXES:
        return suffix

    return ".bin"


def _add_resource(path: Path, resources: dict, zip_files: dict):
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    name = digest + _resource_extension(path)

    resources[name] = {"type": _mime_for_path(path)}
    zip_files[name] = data

    return name


def _base_room():
    # Character-only export.
    #
    # Keep the room entity slot for ZIP compatibility, but do not
    # provide room properties such as backgroundUrl=None that would
    # overwrite the destination room.
    return {}


def _source_values(conn, character_id):
    values = {}

    for row in conn.execute(
        """
        SELECT label, value
        FROM params
        WHERE character_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (character_id,),
    ):
        values[row["label"]] = row["value"]

    for row in conn.execute(
        """
        SELECT label, current_value
        FROM statuses
        WHERE character_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (character_id,),
    ):
        if row["label"] not in values:
            values[row["label"]] = row["current_value"]

    return values


def _validate_derived_values(conn, character_id):
    source_values = _source_values(conn, character_id)
    errors = []

    for row in conn.execute(
        """
        SELECT label, formula
        FROM derived_values
        WHERE character_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (character_id,),
    ):
        formula = str(row["formula"] or "").strip()

        if not formula:
            continue

        try:
            evaluate_formula(formula, source_values)
        except FormulaError as exc:
            errors.append(f"{row['label']}: {exc}")

    if errors:
        raise ValueError(
            "派生値に解決できない式があります。\n"
            "修正してからエクスポートしてください。\n\n"
            + "\n".join(errors[:10])
        )


def _raw_character(conn, character_id):
    _ensure_raw_table(conn)

    row = conn.execute(
        """
        SELECT raw_json
        FROM cocofolia_character_raw
        WHERE character_id = ?
        """,
        (character_id,),
    ).fetchone()

    if row is None:
        return {}

    try:
        value = json.loads(row["raw_json"])
    except Exception:
        return {}

    return value if isinstance(value, dict) else {}


def _commands_for_export(conn, character_id, raw):
    rows = conn.execute(
        """
        SELECT mode, content
        FROM chat_palettes
        WHERE character_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (character_id,),
    ).fetchall()

    normal_contents = [
        str(row["content"] or "")
        for row in rows
        if str(row["mode"] or "normal") == "normal"
        and str(row["content"] or "").strip()
    ]

    if normal_contents:
        return "\n\n".join(normal_contents)

    return str(raw.get("commands", "") or "")


def _memo_for_export(conn, character_id, character, raw):
    rows = conn.execute(
        """
        SELECT title, body, is_private
        FROM memos
        WHERE character_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (character_id,),
    ).fetchall()

    public_rows = [
        row
        for row in rows
        if not bool(row["is_private"])
        and (
            str(row["title"] or "").strip()
            or str(row["body"] or "").strip()
        )
    ]

    if public_rows:
        parts = []

        for row in public_rows:
            title = str(row["title"] or "").strip()
            body = str(row["body"] or "")

            if len(public_rows) == 1 and title == "CCFOLIA Memo":
                parts.append(body)
            elif title:
                parts.append(f"【{title}】\n{body}")
            else:
                parts.append(body)

        return "\n\n".join(parts)

    legacy = str(character["memo"] or "")

    if legacy:
        return legacy

    return str(raw.get("memo", "") or "")


def _character_to_cocofolia(
    conn,
    character_id,
    resources,
    zip_files,
):
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
        raise ValueError("エクスポート対象のキャラクターが見つかりません。")

    # 派生値・技能は管理アプリ側の補助データであり、
    # CCFOLIAキャラクターZIPの必須項目ではない。
    # 未入力の能力値や未解決の派生式が残っていても、
    # エクスポート自体は妨げない。
    raw = _raw_character(conn, character_id)
    data = copy.deepcopy(raw)

    data.update(
        {
            "name": character["name"],
            "memo": _memo_for_export(
                conn,
                character_id,
                character,
                raw,
            ),
            "initiative": _json_number(character["initiative"], 0),
            "externalUrl": str(character["external_url"] or ""),
            "secret": bool(character["secret"]),
            "invisible": bool(character["invisible"]),
            "hideStatus": bool(character["hide_status"]),
            "color": str(character["color"] or "#888888"),
            "commands": _commands_for_export(
                conn,
                character_id,
                raw,
            ),
        }
    )

    statuses = []

    for row in conn.execute(
        """
        SELECT label, current_value, max_value
        FROM statuses
        WHERE character_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (character_id,),
    ):
        if row["current_value"] is None:
            continue

        current = _json_number(row["current_value"], 0)

        maximum = (
            current
            if row["max_value"] is None
            else _json_number(row["max_value"], current)
        )

        statuses.append(
            {
                "label": str(row["label"] or ""),
                "value": current,
                "max": maximum,
            }
        )

    data["status"] = statuses

    data["params"] = [
        {
            "label": str(row["label"] or ""),
            "value": str(row["value"] or ""),
        }
        for row in conn.execute(
            """
            SELECT label, value
            FROM params
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        )
    ]

    image_rows = conn.execute(
        """
        SELECT relative_path, label
        FROM character_images
        WHERE character_id = ?
        ORDER BY sort_order ASC, id ASC
        """,
        (character_id,),
    ).fetchall()

    exported_images = []

    for row in image_rows:
        path = PROJECT_ROOT / row["relative_path"]

        if not path.is_file():
            continue

        resource_name = _add_resource(
            path,
            resources,
            zip_files,
        )

        exported_images.append(
            {
                "resource": resource_name,
                "label": str(row["label"] or ""),
            }
        )

    if exported_images:
        data["iconUrl"] = exported_images[0]["resource"]
        data["faces"] = [
            {
                "iconUrl": row["resource"],
                "label": row["label"],
            }
            for row in exported_images
        ]
    else:
        data["iconUrl"] = None
        data["faces"] = []

    size_row = conn.execute(
        """
        SELECT value
        FROM settings
        WHERE key = 'default_token_size'
        """
    ).fetchone()

    default_size = (
        _json_number(size_row["value"], 4)
        if size_row
        else 4
    )

    data.setdefault("x", 0)
    data.setdefault("y", 0)
    data.setdefault("angle", 0)
    data.setdefault("width", default_size)
    data.setdefault("height", default_size)
    active_row = conn.execute(
        '''
        SELECT value
        FROM settings
        WHERE key = 'cocofolia_token_active'
        '''
    ).fetchone()

    token_active = True

    if active_row is not None:
        token_active = (
            str(
                active_row["value"]
                or ""
            )
            .strip()
            .lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

    # Global send behavior from Settings.
    # Explicitly overwrite imported/raw active state.
    data["active"] = token_active
    data.setdefault("owner", None)

    return character["cocofolia_export_id"], data


def export_characters_to_zip(character_ids, destination_path):
    ids = [
        str(value)
        for value in character_ids
        if str(value).strip()
    ]

    if not ids:
        raise ValueError("エクスポートするキャラクターが選択されていません。")

    resources = {}
    zip_files = {}
    characters = {}
    stored_token = ""

    with get_connection() as conn:
        _ensure_raw_table(conn)

        for character_id in ids:
            export_id, data = _character_to_cocofolia(
                conn,
                character_id,
                resources,
                zip_files,
            )
            characters[export_id] = data

            if not stored_token:
                token_row = conn.execute(
                    """
                    SELECT source_token
                    FROM cocofolia_character_raw
                    WHERE character_id = ?
                    """,
                    (character_id,),
                ).fetchone()

                if token_row and token_row["source_token"]:
                    stored_token = token_row["source_token"]

    payload = {
        "meta": {"version": "1.1.0"},
        "entities": {
            "room": _base_room(),
            "items": {},
            "decks": {},
            "notes": {},
            "characters": characters,
            "effects": {},
            "scenes": {},
            "savedatas": {},
            "snapshots": {},
        },
        "resources": resources,
    }

    destination = Path(destination_path)

    if destination.suffix.lower() != ".zip":
        destination = destination.with_suffix(".zip")

    destination.parent.mkdir(parents=True, exist_ok=True)

    token = stored_token or _new_token()

    with zipfile.ZipFile(
        destination,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            DATA_FILENAME,
            json.dumps(
                payload,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8"),
        )
        archive.writestr(
            TOKEN_FILENAME,
            token.encode("utf-8"),
        )

        for name, data in zip_files.items():
            archive.writestr(name, data)

    return {
        "path": str(destination),
        "characters": len(characters),
        "resources": len(resources),
    }


def default_export_path():
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return EXPORTS_DIR / f"cocofolia_characters_{stamp}.zip"


def _read_zip_json(archive):
    names = set(archive.namelist())

    if DATA_FILENAME not in names:
        raise ValueError("__data.json が見つかりません。")

    try:
        return json.loads(
            archive.read(DATA_FILENAME).decode("utf-8-sig")
        )
    except Exception as exc:
        raise ValueError("__data.json を読み取れません。") from exc


def _resource_bytes(archive, resource_name):
    if not resource_name:
        return None

    name = str(resource_name).replace("\\", "/").lstrip("/")

    if not name or ".." in Path(name).parts:
        return None

    if name not in set(archive.namelist()):
        return None

    return archive.read(name)


def _write_imported_image(character_id, original_name, data):
    suffix = Path(original_name).suffix.lower()

    if suffix not in IMAGE_SUFFIXES:
        suffix = ".png"

    image_id = generate_app_id()
    directory = IMAGES_DIR / character_id
    directory.mkdir(parents=True, exist_ok=True)

    target = directory / f"{image_id}{suffix}"
    target.write_bytes(data)

    relative = target.relative_to(PROJECT_ROOT).as_posix()

    return image_id, relative


def _find_or_create_character(conn, source_id, data):
    existing = conn.execute(
        """
        SELECT id
        FROM characters
        WHERE deleted_at IS NULL
          AND (
            cocofolia_source_id = ?
            OR cocofolia_export_id = ?
          )
        LIMIT 1
        """,
        (source_id, source_id),
    ).fetchone()

    if existing:
        return existing["id"], False

    character_id = generate_app_id()

    collision = conn.execute(
        """
        SELECT 1
        FROM characters
        WHERE cocofolia_export_id = ?
        LIMIT 1
        """,
        (source_id,),
    ).fetchone()

    export_id = (
        generate_unique_cocofolia_id(conn)
        if collision
        else source_id
    )

    conn.execute(
        """
        INSERT INTO characters(
            id,
            name,
            cocofolia_source_id,
            cocofolia_export_id
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            character_id,
            str(data.get("name", "") or "Imported Character"),
            source_id,
            export_id,
        ),
    )

    return character_id, True


def _replace_character_from_raw(
    conn,
    archive,
    source_id,
    character_id,
    data,
    token,
):
    conn.execute(
        """
        UPDATE characters
        SET
            name = ?,
            memo = ?,
            initiative = ?,
            external_url = ?,
            color = ?,
            secret = ?,
            invisible = ?,
            hide_status = ?,
            cocofolia_source_id = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (
            str(data.get("name", "") or "Imported Character"),
            str(data.get("memo", "") or ""),
            _finite_number(data.get("initiative", 0), 0),
            str(data.get("externalUrl", "") or ""),
            str(data.get("color", "#888888") or "#888888"),
            1 if data.get("secret", False) else 0,
            1 if data.get("invisible", False) else 0,
            1 if data.get("hideStatus", False) else 0,
            source_id,
            character_id,
        ),
    )

    conn.execute(
        "DELETE FROM statuses WHERE character_id = ?",
        (character_id,),
    )

    statuses = data.get("status", [])

    if isinstance(statuses, list):
        for index, row in enumerate(statuses):
            if not isinstance(row, dict):
                continue

            try:
                current = float(row.get("value"))
            except (TypeError, ValueError):
                continue

            try:
                maximum = float(row.get("max"))
            except (TypeError, ValueError):
                maximum = current

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
                    str(row.get("label", "") or ""),
                    current,
                    maximum,
                    index,
                ),
            )

    conn.execute(
        "DELETE FROM params WHERE character_id = ?",
        (character_id,),
    )

    params = data.get("params", [])

    if isinstance(params, list):
        for index, row in enumerate(params):
            if not isinstance(row, dict):
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
                    str(row.get("label", "") or ""),
                    str(row.get("value", "") or ""),
                    index,
                ),
            )

    conn.execute(
        "DELETE FROM memos WHERE character_id = ?",
        (character_id,),
    )

    raw_memo = str(data.get("memo", "") or "")

    if raw_memo:
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
            VALUES (?, ?, ?, ?, 0, 0)
            """,
            (
                generate_app_id(),
                character_id,
                "CCFOLIA Memo",
                raw_memo,
            ),
        )

    conn.execute(
        "DELETE FROM chat_palettes WHERE character_id = ?",
        (character_id,),
    )

    commands = str(data.get("commands", "") or "")

    if commands:
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
                "CCFOLIA Import",
                commands,
            ),
        )

    conn.execute(
        "DELETE FROM character_images WHERE character_id = ?",
        (character_id,),
    )

    image_sources = []
    icon_url = data.get("iconUrl")
    faces = data.get("faces", [])
    face_labels = {}

    if isinstance(faces, list):
        for face in faces:
            if not isinstance(face, dict):
                continue

            face_url = face.get("iconUrl")

            if face_url:
                face_labels[str(face_url)] = str(
                    face.get("label", "") or ""
                )

    if icon_url:
        image_sources.append(
            (
                str(icon_url),
                face_labels.get(str(icon_url), ""),
            )
        )

    if isinstance(faces, list):
        for face in faces:
            if not isinstance(face, dict):
                continue

            face_url = face.get("iconUrl")

            if face_url:
                image_sources.append(
                    (
                        str(face_url),
                        str(face.get("label", "") or ""),
                    )
                )

    seen = set()
    sort_order = 0

    for resource_name, label in image_sources:
        if resource_name in seen:
            continue

        seen.add(resource_name)

        image_data = _resource_bytes(
            archive,
            resource_name,
        )

        if image_data is None:
            continue

        image_id, relative = _write_imported_image(
            character_id,
            resource_name,
            image_data,
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
                character_id,
                relative,
                label,
                sort_order,
            ),
        )

        sort_order += 1

    _ensure_raw_table(conn)

    conn.execute(
        """
        INSERT INTO cocofolia_character_raw(
            character_id,
            source_character_id,
            raw_json,
            source_token,
            imported_at
        )
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(character_id)
        DO UPDATE SET
            source_character_id = excluded.source_character_id,
            raw_json = excluded.raw_json,
            source_token = excluded.source_token,
            imported_at = CURRENT_TIMESTAMP
        """,
        (
            character_id,
            source_id,
            json.dumps(data, ensure_ascii=False),
            token,
        ),
    )


def import_room_zip(zip_path, template="generic"):
    source = Path(zip_path)

    if not source.is_file():
        raise ValueError("ZIPファイルが見つかりません。")

    imported = []

    with zipfile.ZipFile(source, "r") as archive:
        payload = _read_zip_json(archive)

        if not isinstance(payload, dict):
            raise ValueError("__data.json の形式が不正です。")

        names = set(archive.namelist())
        token = ""

        if TOKEN_FILENAME in names:
            token = (
                archive.read(TOKEN_FILENAME)
                .decode("utf-8", errors="replace")
                .strip()
            )

        entities = payload.get("entities", {})

        if not isinstance(entities, dict):
            raise ValueError("entities の形式が不正です。")

        characters = entities.get("characters", {})

        if not isinstance(characters, dict):
            raise ValueError("characters の形式が不正です。")

        if not characters:
            raise ValueError("このZIPにはキャラクターが含まれていません。")

        with get_connection() as conn:
            _ensure_raw_table(conn)

            for source_id, data in characters.items():
                if not isinstance(data, dict):
                    continue

                source_id = str(source_id).strip()

                if not source_id:
                    continue

                character_id, created = _find_or_create_character(
                    conn,
                    source_id,
                    data,
                )

                _replace_character_from_raw(
                    conn,
                    archive,
                    source_id,
                    character_id,
                    data,
                    token,
                )

                imported.append(
                    {
                        "id": character_id,
                        "name": str(
                            data.get("name", "")
                            or "Imported Character"
                        ),
                        "created": created,
                    }
                )

    if template == "coc6":
        for item in imported:
            apply_coc6_template(item["id"])

    return imported
