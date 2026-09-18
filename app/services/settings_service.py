from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.db.database import get_connection


DEFAULTS = {
    "autosave_enabled": "1",
    "autosave_delay_ms": "750",
    "font_size": "medium",
    "default_token_size": "4",
    "developer_mode": "0",
    "cocofolia_token_active": "1",
}

FONT_SIZES = {
    "small": {"base": 12, "section": 12, "dialog": 17, "character": 20},
    "medium": {"base": 13, "section": 13, "dialog": 18, "character": 22},
    "large": {"base": 15, "section": 15, "dialog": 21, "character": 25},
}

FONT_MARKER_START = "/* CCM_DYNAMIC_FONT_START */"
FONT_MARKER_END = "/* CCM_DYNAMIC_FONT_END */"


def get_setting(key: str, default=None):
    if default is None:
        default = DEFAULTS.get(key, "")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?",
            (key,),
        ).fetchone()

    if row is None:
        return default

    return str(row["value"])


def set_setting(key: str, value):
    with get_connection() as conn:
        conn.execute(
            '''
            INSERT INTO settings(key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            ''',
            (key, str(value)),
        )


def get_bool_setting(key: str, default=False):
    fallback = "1" if default else "0"
    value = get_setting(key, fallback).strip().lower()

    return value in {"1", "true", "yes", "on"}


def get_int_setting(
    key: str,
    default: int,
    minimum=None,
    maximum=None,
):
    try:
        value = int(
            get_setting(
                key,
                str(default),
            )
        )
    except (
        TypeError,
        ValueError,
    ):
        value = default

    if minimum is not None:
        value = max(
            minimum,
            value,
        )

    if maximum is not None:
        value = min(
            maximum,
            value,
        )

    return value


def load_settings():
    font_size = get_setting(
        "font_size",
        "medium",
    )

    if font_size not in FONT_SIZES:
        font_size = "medium"

    return {
        "autosave_enabled": get_bool_setting(
            "autosave_enabled",
            True,
        ),
        "autosave_delay_ms": get_int_setting(
            "autosave_delay_ms",
            750,
            minimum=250,
            maximum=5000,
        ),
        "font_size": font_size,
        "default_token_size": get_int_setting(
            "default_token_size",
            4,
            minimum=1,
            maximum=20,
        ),
        "developer_mode": get_bool_setting(
            "developer_mode",
            False,
        ),
        "cocofolia_token_active": get_bool_setting(
            "cocofolia_token_active",
            True,
        ),
    }


def save_settings(values: dict):
    set_setting(
        "autosave_enabled",
        "1"
        if values.get(
            "autosave_enabled",
            True,
        )
        else "0",
    )

    set_setting(
        "autosave_delay_ms",
        int(
            values.get(
                "autosave_delay_ms",
                750,
            )
        ),
    )

    font_size = str(
        values.get(
            "font_size",
            "medium",
        )
    )

    if font_size not in FONT_SIZES:
        font_size = "medium"

    set_setting(
        "font_size",
        font_size,
    )

    set_setting(
        "default_token_size",
        int(
            values.get(
                "default_token_size",
                4,
            )
        ),
    )

    set_setting(
        "developer_mode",
        "1"
        if values.get(
            "developer_mode",
            False,
        )
        else "0",
    )

    set_setting(
        "cocofolia_token_active",
        "1"
        if values.get(
            "cocofolia_token_active",
            True,
        )
        else "0",
    )


def _strip_dynamic_font(stylesheet: str):
    start = stylesheet.find(
        FONT_MARKER_START
    )

    if start < 0:
        return stylesheet

    end = stylesheet.find(
        FONT_MARKER_END,
        start,
    )

    if end < 0:
        return stylesheet[
            :start
        ].rstrip()

    end += len(
        FONT_MARKER_END
    )

    return (
        stylesheet[:start]
        + stylesheet[end:]
    ).rstrip()


def apply_ui_font_size(app=None):
    if app is None:
        app = QApplication.instance()

    if app is None:
        return

    size_name = get_setting(
        "font_size",
        "medium",
    )

    sizes = FONT_SIZES.get(
        size_name,
        FONT_SIZES["medium"],
    )

    base_stylesheet = _strip_dynamic_font(
        app.styleSheet()
    )

    dynamic = f'''
{FONT_MARKER_START}
QWidget {{
    font-size: {sizes['base']}px;
}}
#AppTitle,
#SectionTitle {{
    font-size: {sizes['section']}px;
}}
#DialogTitle {{
    font-size: {sizes['dialog']}px;
}}
#CharacterName {{
    font-size: {sizes['character']}px;
}}
{FONT_MARKER_END}
'''

    app.setStyleSheet(
        base_stylesheet
        + "\n"
        + dynamic
    )
