from __future__ import annotations

from app.db.database import get_connection
from app.ids import generate_app_id
from app.services.advanced_service import (
    COC6_SKILLS,
    load_advanced_bundle,
    save_advanced_bundle,
)
from app.services.character_service import (
    get_character_bundle,
    save_character_bundle,
)
from app.services.formula_engine import (
    FormulaError as LegacyFormulaError,
    resolve_value_text,
)
from app.services.rule_data_service import (
    apply_rule_template,
    ensure_phase22a_schema,
    recalculate_character_formulas,
)
from app.services.rule_formula_engine import (
    FormulaError,
    evaluate_formula,
    format_formula_value,
)


def _row_text(row: dict, key: str) -> str:
    value = row.get(key, "")
    return "" if value is None else str(value)


def _status_rows_for_legacy_save(rows: list[dict]) -> list[dict]:
    output = []

    for row in rows:
        label = _row_text(row, "label").strip()
        current = _row_text(row, "current").strip()
        maximum = _row_text(row, "max").strip()

        if not label and not current and not maximum:
            continue

        output.append(
            {
                "label": label,
                "current": current,
                "max": maximum,
            }
        )

    return output


def _param_rows_for_legacy_save(rows: list[dict]) -> list[dict]:
    output = []

    for row in rows:
        label = _row_text(row, "label").strip()
        value = _row_text(row, "value")

        if not label and not value.strip():
            continue

        output.append(
            {
                "label": label,
                "value": value,
            }
        )

    return output


def load_v22_bundle(character_id: str) -> dict:
    ensure_phase22a_schema()
    return get_character_bundle(character_id)


def save_v22_bundle(
    character_id: str,
    character_data: dict,
    images: list[dict],
    statuses: list[dict],
    params: list[dict],
    memos: list[dict],
    tag_names: list[str],
    group_ids: list[str],
    template_id: str = "",
) -> dict:
    ensure_phase22a_schema()

    clean_statuses = _status_rows_for_legacy_save(statuses)
    clean_params = _param_rows_for_legacy_save(params)

    save_character_bundle(
        character_id,
        character_data,
        images,
        clean_statuses,
        clean_params,
        memos,
        tag_names,
        group_ids,
    )

    status_meta = [
        row
        for row in statuses
        if (
            _row_text(row, "label").strip()
            or _row_text(row, "current").strip()
            or _row_text(row, "max").strip()
        )
    ]

    param_meta = [
        row
        for row in params
        if (
            _row_text(row, "label").strip()
            or _row_text(row, "value").strip()
        )
    ]

    with get_connection() as conn:
        status_db = conn.execute(
            """
            SELECT id
            FROM statuses
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        for db_row, meta in zip(status_db, status_meta):
            conn.execute(
                """
                UPDATE statuses
                SET
                    initial_formula = ?,
                    max_formula = ?,
                    formula_error = ''
                WHERE id = ?
                """,
                (
                    _row_text(meta, "initial_formula").strip(),
                    _row_text(meta, "max_formula").strip(),
                    db_row["id"],
                ),
            )

        param_db = conn.execute(
            """
            SELECT id
            FROM params
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        for db_row, meta in zip(param_db, param_meta):
            conn.execute(
                """
                UPDATE params
                SET
                    formula = ?,
                    formula_error = ''
                WHERE id = ?
                """,
                (
                    _row_text(meta, "formula").strip(),
                    db_row["id"],
                ),
            )

        columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(characters)"
            ).fetchall()
        }

        if "template_id" in columns:
            conn.execute(
                """
                UPDATE characters
                SET template_id = ?
                WHERE id = ?
                """,
                (
                    str(template_id or ""),
                    character_id,
                ),
            )

    recalculate_character_formulas(
        character_id,
        apply_initial_status=False,
    )

    return get_character_bundle(character_id)


def save_skills_and_palettes(
    character_id: str,
    skills: list[dict],
    palettes: list[dict],
) -> None:
    advanced = load_advanced_bundle(
        character_id
    )

    save_advanced_bundle(
        character_id,
        advanced["derived"],
        skills,
        palettes,
    )


def apply_template_v22(
    character_id: str,
    template_id: str,
) -> None:
    ensure_phase22a_schema()

    apply_rule_template(
        character_id,
        template_id,
        fill_missing_only=True,
        apply_initial_status=True,
    )

    if template_id != "coc6":
        return

    with get_connection() as conn:
        skill_columns = {
            row["name"]
            for row in conn.execute(
                "PRAGMA table_info(skills)"
            ).fetchall()
        }

        if "category" not in skill_columns:
            conn.execute(
                """
                ALTER TABLE skills
                ADD COLUMN category TEXT NOT NULL DEFAULT ''
                """
            )

        existing_rows = conn.execute(
            """
            SELECT id, label, category
            FROM skills
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()

        existing_by_label = {
            row["label"]: row
            for row in existing_rows
        }

        next_order = conn.execute(
            """
            SELECT
                COALESCE(MAX(sort_order), -1) + 1 AS n
            FROM skills
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()["n"]

        for label, value, category in COC6_SKILLS:
            existing = existing_by_label.get(label)

            if existing is not None:
                if not str(
                    existing["category"]
                    or ""
                ).strip():
                    conn.execute(
                        """
                        UPDATE skills
                        SET category = ?
                        WHERE id = ?
                        """,
                        (
                            category,
                            existing["id"],
                        ),
                    )
                continue

            conn.execute(
                """
                INSERT INTO skills(
                    id,
                    character_id,
                    label,
                    value,
                    category,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_app_id(),
                    character_id,
                    label,
                    value,
                    category,
                    next_order,
                ),
            )

            next_order += 1


def reset_status_initial_values(
    character_id: str,
) -> None:
    recalculate_character_formulas(
        character_id,
        apply_initial_status=True,
    )


def generate_coc6_palette_v22(
    character_id: str,
) -> str:
    ensure_phase22a_schema()

    with get_connection() as conn:
        params = conn.execute(
            """
            SELECT label, value
            FROM params
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        statuses = conn.execute(
            """
            SELECT label, current_value
            FROM statuses
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

        skills = conn.execute(
            """
            SELECT label, value
            FROM skills
            WHERE character_id = ?
            ORDER BY sort_order ASC, id ASC
            """,
            (character_id,),
        ).fetchall()

    values = {}

    for row in params:
        values[row["label"]] = row["value"]

    for row in statuses:
        if row["label"] not in values:
            values[row["label"]] = row["current_value"]

    lines = []

    for label in (
        "SAN",
        "アイデア",
        "幸運",
        "知識",
    ):
        value = values.get(label)

        if value not in (
            None,
            "",
        ):
            lines.append(
                f"CCB<={value} {label}"
            )

    if lines:
        lines.append("")

    for row in skills:
        try:
            result, error = resolve_value_text(
                str(row["value"] or ""),
                values,
            )
        except LegacyFormulaError:
            continue

        if result and not error:
            lines.append(
                f"CCB<={result} {row['label']}"
            )

    return "\n".join(lines).strip()
