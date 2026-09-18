from __future__ import annotations

from collections import OrderedDict

from app.db.database import get_connection
from app.ids import generate_app_id
from app.services.rule_formula_engine import (
    FormulaError,
    evaluate_formula,
    format_formula_value,
)
from app.services.rule_templates import (
    get_rule_template,
)


PHASE22A_SCHEMA_VERSION = "1"


def _columns(
    conn,
    table_name: str,
):
    try:
        rows = conn.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    except Exception:
        return set()

    result = set()

    for row in rows:
        try:
            result.add(
                row["name"]
            )
        except Exception:
            result.add(
                row[1]
            )

    return result


def _table_exists(
    conn,
    table_name: str,
):
    row = conn.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table'
          AND name = ?
        """,
        (
            table_name,
        ),
    ).fetchone()

    return row is not None


def _add_column_if_missing(
    conn,
    table_name: str,
    column_name: str,
    definition: str,
):
    if not _table_exists(
        conn,
        table_name,
    ):
        return

    if column_name in _columns(
        conn,
        table_name,
    ):
        return

    conn.execute(
        f"""
        ALTER TABLE {table_name}
        ADD COLUMN {column_name} {definition}
        """
    )


def ensure_phase22a_schema():
    with get_connection() as conn:
        _add_column_if_missing(
            conn,
            "characters",
            "template_id",
            "TEXT NOT NULL DEFAULT ''",
        )

        _add_column_if_missing(
            conn,
            "statuses",
            "initial_formula",
            "TEXT NOT NULL DEFAULT ''",
        )
        _add_column_if_missing(
            conn,
            "statuses",
            "max_formula",
            "TEXT NOT NULL DEFAULT ''",
        )
        _add_column_if_missing(
            conn,
            "statuses",
            "formula_error",
            "TEXT NOT NULL DEFAULT ''",
        )

        _add_column_if_missing(
            conn,
            "params",
            "formula",
            "TEXT NOT NULL DEFAULT ''",
        )
        _add_column_if_missing(
            conn,
            "params",
            "formula_error",
            "TEXT NOT NULL DEFAULT ''",
        )

        if _table_exists(
            conn,
            "settings",
        ):
            conn.execute(
                """
                INSERT INTO settings(
                    key,
                    value
                )
                VALUES(
                    'developer_mode',
                    '0'
                )
                ON CONFLICT(key)
                DO NOTHING
                """
            )

            conn.execute(
                """
                INSERT INTO settings(
                    key,
                    value
                )
                VALUES(
                    'phase22a_schema_version',
                    ?
                )
                ON CONFLICT(key)
                DO UPDATE SET
                    value = excluded.value
                """,
                (
                    PHASE22A_SCHEMA_VERSION,
                ),
            )


def _row_value(
    row,
    key,
    default="",
):
    try:
        value = row[
            key
        ]
    except Exception:
        return default

    if value is None:
        return default

    return value


def _find_status(
    conn,
    character_id: str,
    label: str,
):
    return conn.execute(
        """
        SELECT *
        FROM statuses
        WHERE character_id = ?
          AND label = ?
        ORDER BY sort_order ASC, id ASC
        LIMIT 1
        """,
        (
            character_id,
            label,
        ),
    ).fetchone()


def _find_param(
    conn,
    character_id: str,
    label: str,
):
    return conn.execute(
        """
        SELECT *
        FROM params
        WHERE character_id = ?
          AND label = ?
        ORDER BY sort_order ASC, id ASC
        LIMIT 1
        """,
        (
            character_id,
            label,
        ),
    ).fetchone()


def migrate_legacy_derived_values():
    """
    Legacy derived_values is intentionally preserved.

    Each legacy row is mirrored into the new model:
      - matching status -> formula metadata on that status
      - otherwise -> formula-bearing param

    Running this repeatedly is safe.  This matters during Phase 22A
    because the old UI may still edit derived_values before Phase 22B.
    """

    ensure_phase22a_schema()

    migrated_statuses = 0
    migrated_params = 0

    with get_connection() as conn:
        if not _table_exists(
            conn,
            "derived_values",
        ):
            return {
                "statuses": 0,
                "params": 0,
            }

        rows = conn.execute(
            """
            SELECT *
            FROM derived_values
            ORDER BY
                character_id ASC,
                sort_order ASC,
                id ASC
            """
        ).fetchall()

        for row in rows:
            character_id = str(
                _row_value(
                    row,
                    "character_id",
                    "",
                )
            )
            label = str(
                _row_value(
                    row,
                    "label",
                    "",
                )
            ).strip()
            formula = str(
                _row_value(
                    row,
                    "formula",
                    "",
                )
            ).strip()
            error = str(
                _row_value(
                    row,
                    "error",
                    "",
                )
            ).strip()
            last_value = _row_value(
                row,
                "last_value",
                "",
            )

            if (
                not character_id
                or not label
                or not formula
            ):
                continue

            status = _find_status(
                conn,
                character_id,
                label,
            )

            if status is not None:
                existing_initial = str(
                    _row_value(
                        status,
                        "initial_formula",
                        "",
                    )
                ).strip()
                existing_max = str(
                    _row_value(
                        status,
                        "max_formula",
                        "",
                    )
                ).strip()

                initial_formula = (
                    existing_initial
                    or formula
                )
                max_formula = (
                    existing_max
                )

                # Current CoC6 legacy semantics:
                # HP/MP are both initial and maximum derived values.
                # SAN's initial value is derived, but its maximum is normally fixed.
                if (
                    not max_formula
                    and label
                    in {
                        "HP",
                        "MP",
                    }
                ):
                    max_formula = formula

                conn.execute(
                    """
                    UPDATE statuses
                    SET
                        initial_formula = ?,
                        max_formula = ?,
                        formula_error = ?
                    WHERE id = ?
                    """,
                    (
                        initial_formula,
                        max_formula,
                        error,
                        status[
                            "id"
                        ],
                    ),
                )

                migrated_statuses += 1
                continue

            param = _find_param(
                conn,
                character_id,
                label,
            )

            if param is not None:
                existing_formula = str(
                    _row_value(
                        param,
                        "formula",
                        "",
                    )
                ).strip()

                conn.execute(
                    """
                    UPDATE params
                    SET
                        formula = ?,
                        formula_error = ?
                    WHERE id = ?
                    """,
                    (
                        existing_formula
                        or formula,
                        error,
                        param[
                            "id"
                        ],
                    ),
                )

                migrated_params += 1
                continue

            sort_row = conn.execute(
                """
                SELECT
                    COALESCE(
                        MAX(sort_order),
                        -1
                    ) + 1
                    AS next_order
                FROM params
                WHERE character_id = ?
                """,
                (
                    character_id,
                ),
            ).fetchone()

            try:
                next_order = int(
                    sort_row[
                        "next_order"
                    ]
                )
            except Exception:
                next_order = 0

            conn.execute(
                """
                INSERT INTO params(
                    id,
                    character_id,
                    label,
                    value,
                    sort_order,
                    formula,
                    formula_error
                )
                VALUES(
                    ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    generate_app_id(),
                    character_id,
                    label,
                    str(
                        last_value
                        if last_value
                        is not None
                        else ""
                    ),
                    next_order,
                    formula,
                    error,
                ),
            )

            migrated_params += 1

    return {
        "statuses": migrated_statuses,
        "params": migrated_params,
    }


def _character_values(
    conn,
    character_id: str,
):
    values = OrderedDict()

    rows = conn.execute(
        """
        SELECT
            label,
            value
        FROM params
        WHERE character_id = ?
        ORDER BY
            sort_order ASC,
            id ASC
        """,
        (
            character_id,
        ),
    ).fetchall()

    for row in rows:
        label = str(
            row[
                "label"
            ]
            or ""
        ).strip()

        if label:
            values[
                label
            ] = row[
                "value"
            ]

    return values


def recalculate_character_formulas(
    character_id: str,
    *,
    apply_initial_status: bool = False,
):
    """
    Recalculate formula-bearing params and status metadata.

    Param formulas are iterated so one computed param can refer to another.
    Status initial_formula is only copied into current_value when explicitly
    requested (template application / reset), never during ordinary refresh.
    max_formula is safe to refresh because it represents the ceiling/cap.
    """

    ensure_phase22a_schema()

    with get_connection() as conn:
        values = _character_values(
            conn,
            character_id,
        )

        param_rows = conn.execute(
            """
            SELECT *
            FROM params
            WHERE character_id = ?
              AND TRIM(
                    COALESCE(
                        formula,
                        ''
                    )
                  ) <> ''
            ORDER BY
                sort_order ASC,
                id ASC
            """,
            (
                character_id,
            ),
        ).fetchall()

        pending = list(
            param_rows
        )

        for _ in range(
            max(
                1,
                len(
                    pending
                )
                + 1,
            )
        ):
            if not pending:
                break

            next_pending = []
            progress = False

            for row in pending:
                formula = str(
                    row[
                        "formula"
                    ]
                    or ""
                ).strip()
                label = str(
                    row[
                        "label"
                    ]
                    or ""
                ).strip()

                try:
                    result = evaluate_formula(
                        formula,
                        values,
                    )
                except FormulaError as exc:
                    next_pending.append(
                        row
                    )

                    conn.execute(
                        """
                        UPDATE params
                        SET formula_error = ?
                        WHERE id = ?
                        """,
                        (
                            str(
                                exc
                            ),
                            row[
                                "id"
                            ],
                        ),
                    )
                    continue

                text_value = (
                    format_formula_value(
                        result
                    )
                )

                conn.execute(
                    """
                    UPDATE params
                    SET
                        value = ?,
                        formula_error = ''
                    WHERE id = ?
                    """,
                    (
                        text_value,
                        row[
                            "id"
                        ],
                    ),
                )

                values[
                    label
                ] = text_value
                progress = True

            pending = next_pending

            if not progress:
                break

        status_rows = conn.execute(
            """
            SELECT *
            FROM statuses
            WHERE character_id = ?
            ORDER BY
                sort_order ASC,
                id ASC
            """,
            (
                character_id,
            ),
        ).fetchall()

        for row in status_rows:
            initial_formula = str(
                _row_value(
                    row,
                    "initial_formula",
                    "",
                )
            ).strip()
            max_formula = str(
                _row_value(
                    row,
                    "max_formula",
                    "",
                )
            ).strip()

            errors = []

            if max_formula:
                try:
                    result = evaluate_formula(
                        max_formula,
                        values,
                    )

                    conn.execute(
                        """
                        UPDATE statuses
                        SET max_value = ?
                        WHERE id = ?
                        """,
                        (
                            result,
                            row[
                                "id"
                            ],
                        ),
                    )
                except FormulaError as exc:
                    errors.append(
                        f"最大値: {exc}"
                    )

            if (
                apply_initial_status
                and initial_formula
            ):
                try:
                    result = evaluate_formula(
                        initial_formula,
                        values,
                    )

                    conn.execute(
                        """
                        UPDATE statuses
                        SET current_value = ?
                        WHERE id = ?
                        """,
                        (
                            result,
                            row[
                                "id"
                            ],
                        ),
                    )
                except FormulaError as exc:
                    errors.append(
                        f"初期値: {exc}"
                    )

            conn.execute(
                """
                UPDATE statuses
                SET formula_error = ?
                WHERE id = ?
                """,
                (
                    " / ".join(
                        errors
                    ),
                    row[
                        "id"
                    ],
                ),
            )


def recalculate_all_formula_fields():
    ensure_phase22a_schema()

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM characters
            WHERE deleted_at IS NULL
            """
        ).fetchall()

        ids = [
            row[
                "id"
            ]
            for row in rows
        ]

    for character_id in ids:
        recalculate_character_formulas(
            character_id,
            apply_initial_status=False,
        )


def _next_sort_order(
    conn,
    table_name: str,
    character_id: str,
):
    row = conn.execute(
        f"""
        SELECT
            COALESCE(
                MAX(sort_order),
                -1
            ) + 1 AS next_order
        FROM {table_name}
        WHERE character_id = ?
        """,
        (
            character_id,
        ),
    ).fetchone()

    try:
        return int(
            row[
                "next_order"
            ]
        )
    except Exception:
        return 0


def apply_rule_template(
    character_id: str,
    template_id: str,
    *,
    fill_missing_only: bool = True,
    apply_initial_status: bool = True,
):
    """
    Declarative rule-template application for Phase 22B and later.

    Existing raw values are preserved.  Missing formula metadata can be
    filled without overwriting imported/manual values.
    """

    ensure_phase22a_schema()

    template = get_rule_template(
        template_id
    )

    if template is None:
        raise ValueError(
            f"未知のテンプレートです: {template_id}"
        )

    with get_connection() as conn:
        for spec in template.get(
            "params",
            [],
        ):
            label = str(
                spec.get(
                    "label",
                    "",
                )
            ).strip()

            if not label:
                continue

            formula = str(
                spec.get(
                    "formula",
                    "",
                )
            ).strip()

            row = _find_param(
                conn,
                character_id,
                label,
            )

            if row is None:
                conn.execute(
                    """
                    INSERT INTO params(
                        id,
                        character_id,
                        label,
                        value,
                        sort_order,
                        formula,
                        formula_error
                    )
                    VALUES(
                        ?, ?, ?, ?, ?, ?, ''
                    )
                    """,
                    (
                        generate_app_id(),
                        character_id,
                        label,
                        str(
                            spec.get(
                                "value",
                                "",
                            )
                        ),
                        _next_sort_order(
                            conn,
                            "params",
                            character_id,
                        ),
                        formula,
                    ),
                )
            elif formula:
                existing_formula = str(
                    _row_value(
                        row,
                        "formula",
                        "",
                    )
                ).strip()

                if (
                    not fill_missing_only
                    or not existing_formula
                ):
                    conn.execute(
                        """
                        UPDATE params
                        SET formula = ?
                        WHERE id = ?
                        """,
                        (
                            formula,
                            row[
                                "id"
                            ],
                        ),
                    )

        for spec in template.get(
            "statuses",
            [],
        ):
            label = str(
                spec.get(
                    "label",
                    "",
                )
            ).strip()

            if not label:
                continue

            initial_formula = str(
                spec.get(
                    "initial_formula",
                    "",
                )
            ).strip()
            max_formula = str(
                spec.get(
                    "max_formula",
                    "",
                )
            ).strip()

            row = _find_status(
                conn,
                character_id,
                label,
            )

            if row is None:
                conn.execute(
                    """
                    INSERT INTO statuses(
                        id,
                        character_id,
                        label,
                        current_value,
                        max_value,
                        sort_order,
                        initial_formula,
                        max_formula,
                        formula_error
                    )
                    VALUES(
                        ?, ?, ?, ?, ?, ?, ?, ?, ''
                    )
                    """,
                    (
                        generate_app_id(),
                        character_id,
                        label,
                        spec.get(
                            "current_value",
                            None,
                        ),
                        spec.get(
                            "max_value",
                            None,
                        ),
                        _next_sort_order(
                            conn,
                            "statuses",
                            character_id,
                        ),
                        initial_formula,
                        max_formula,
                    ),
                )
            else:
                updates = []
                args = []

                existing_initial = str(
                    _row_value(
                        row,
                        "initial_formula",
                        "",
                    )
                ).strip()
                existing_max = str(
                    _row_value(
                        row,
                        "max_formula",
                        "",
                    )
                ).strip()

                if (
                    initial_formula
                    and (
                        not fill_missing_only
                        or not existing_initial
                    )
                ):
                    updates.append(
                        "initial_formula = ?"
                    )
                    args.append(
                        initial_formula
                    )

                if (
                    max_formula
                    and (
                        not fill_missing_only
                        or not existing_max
                    )
                ):
                    updates.append(
                        "max_formula = ?"
                    )
                    args.append(
                        max_formula
                    )

                if (
                    spec.get(
                        "max_value",
                        None,
                    )
                    is not None
                    and _row_value(
                        row,
                        "max_value",
                        None,
                    )
                    in (
                        None,
                        "",
                    )
                ):
                    updates.append(
                        "max_value = ?"
                    )
                    args.append(
                        spec[
                            "max_value"
                        ]
                    )

                if updates:
                    args.append(
                        row[
                            "id"
                        ]
                    )

                    conn.execute(
                        f"""
                        UPDATE statuses
                        SET {', '.join(updates)}
                        WHERE id = ?
                        """,
                        args,
                    )

        if "template_id" in _columns(
            conn,
            "characters",
        ):
            conn.execute(
                """
                UPDATE characters
                SET template_id = ?
                WHERE id = ?
                """,
                (
                    template_id,
                    character_id,
                ),
            )

    recalculate_character_formulas(
        character_id,
        apply_initial_status=(
            apply_initial_status
        ),
    )
