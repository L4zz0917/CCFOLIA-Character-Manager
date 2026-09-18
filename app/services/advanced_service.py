from __future__ import annotations

from app.db.database import get_connection
from app.ids import generate_app_id
from app.services.formula_engine import (
    FormulaError,
    evaluate_formula,
    resolve_value_text,
)


SKILL_CATEGORIES = [
    "戦闘技能",
    "探索技能",
    "行動技能",
    "交渉技能",
    "知識技能",
]

COC6_PARAMS = [
    "STR",
    "CON",
    "POW",
    "DEX",
    "APP",
    "SIZ",
    "INT",
    "EDU",
]

COC6_DERIVED = [
    ("HP", "ceil(([CON]+[SIZ])/2)"),
    ("MP", "[POW]"),
    ("SAN", "[POW]*5"),
    ("アイデア", "[INT]*5"),
    ("幸運", "[POW]*5"),
    ("知識", "[EDU]*5"),
    ("DB", "db6([STR]+[SIZ])"),
    ("職業技能P", "[EDU]*20"),
    ("趣味技能P", "[INT]*10"),
]

# 技能名・初期値はKADOKAWA公式クラシック版現代探索者シートを基準。
# categoryは管理UI用の整理区分（戦闘/探索/行動/交渉/知識）。
COC6_SKILLS = [
    ("回避", "[DEX]*2", "戦闘技能"),
    ("キック", "25", "戦闘技能"),
    ("組み付き", "25", "戦闘技能"),
    ("こぶし", "50", "戦闘技能"),
    ("頭突き", "10", "戦闘技能"),
    ("投擲", "25", "戦闘技能"),
    ("マーシャルアーツ", "1", "戦闘技能"),
    ("拳銃", "20", "戦闘技能"),
    ("サブマシンガン", "15", "戦闘技能"),
    ("ショットガン", "30", "戦闘技能"),
    ("マシンガン", "15", "戦闘技能"),
    ("ライフル", "25", "戦闘技能"),

    ("応急手当", "30", "探索技能"),
    ("鍵開け", "1", "探索技能"),
    ("隠す", "15", "探索技能"),
    ("隠れる", "10", "探索技能"),
    ("聞き耳", "25", "探索技能"),
    ("忍び歩き", "10", "探索技能"),
    ("写真術", "10", "探索技能"),
    ("精神分析", "1", "探索技能"),
    ("追跡", "10", "探索技能"),
    ("登攀", "40", "探索技能"),
    ("図書館", "25", "探索技能"),
    ("目星", "25", "探索技能"),

    ("運転（自動車）", "20", "行動技能"),
    ("機械修理", "20", "行動技能"),
    ("重機械操作", "1", "行動技能"),
    ("乗馬", "5", "行動技能"),
    ("水泳", "25", "行動技能"),
    ("製作", "5", "行動技能"),
    ("操縦", "1", "行動技能"),
    ("跳躍", "25", "行動技能"),
    ("電気修理", "10", "行動技能"),
    ("ナビゲート", "10", "行動技能"),
    ("変装", "1", "行動技能"),

    ("言いくるめ", "5", "交渉技能"),
    ("信用", "15", "交渉技能"),
    ("説得", "15", "交渉技能"),
    ("値切り", "5", "交渉技能"),
    ("母国語", "[EDU]*5", "交渉技能"),
    ("ほかの言語", "1", "交渉技能"),

    ("医学", "5", "知識技能"),
    ("オカルト", "5", "知識技能"),
    ("化学", "1", "知識技能"),
    ("クトゥルフ神話", "0", "知識技能"),
    ("芸術", "5", "知識技能"),
    ("経理", "10", "知識技能"),
    ("考古学", "1", "知識技能"),
    ("コンピューター", "1", "知識技能"),
    ("心理学", "5", "知識技能"),
    ("人類学", "1", "知識技能"),
    ("生物学", "1", "知識技能"),
    ("地質学", "1", "知識技能"),
    ("電子工学", "1", "知識技能"),
    ("天文学", "1", "知識技能"),
    ("博物学", "10", "知識技能"),
    ("物理学", "1", "知識技能"),
    ("法律", "5", "知識技能"),
    ("薬学", "1", "知識技能"),
    ("歴史", "20", "知識技能"),
]

COC6_SKILL_CATEGORY_MAP = {
    label: category
    for label, _, category in COC6_SKILLS
}


def _ensure_skill_schema(conn):
    columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(skills)").fetchall()
    }

    if "category" not in columns:
        conn.execute(
            "ALTER TABLE skills ADD COLUMN category TEXT NOT NULL DEFAULT ''"
        )


def _source_values(conn, character_id: str) -> dict[str, object]:
    output = {}

    for row in conn.execute(
        """
        SELECT label, value
        FROM params
        WHERE character_id = ?
        ORDER BY sort_order ASC
        """,
        (character_id,),
    ):
        output[row["label"]] = row["value"]

    for row in conn.execute(
        """
        SELECT label, current_value
        FROM statuses
        WHERE character_id = ?
        ORDER BY sort_order ASC
        """,
        (character_id,),
    ):
        if row["label"] not in output:
            output[row["label"]] = row["current_value"]

    return output


def _backfill_skill_categories(conn, character_id: str) -> None:
    _ensure_skill_schema(conn)

    rows = conn.execute(
        """
        SELECT id, label, category
        FROM skills
        WHERE character_id = ?
        """,
        (character_id,),
    ).fetchall()

    for row in rows:
        if str(row["category"] or "").strip():
            continue

        category = COC6_SKILL_CATEGORY_MAP.get(row["label"])
        if category:
            conn.execute(
                "UPDATE skills SET category = ? WHERE id = ?",
                (category, row["id"]),
            )


def get_source_values(character_id: str) -> dict[str, object]:
    with get_connection() as conn:
        return _source_values(conn, character_id)


def load_advanced_bundle(character_id: str) -> dict:
    with get_connection() as conn:
        _ensure_skill_schema(conn)
        _backfill_skill_categories(conn, character_id)

        derived = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM derived_values
                WHERE character_id = ?
                ORDER BY sort_order ASC, id ASC
                """,
                (character_id,),
            ).fetchall()
        ]

        skills = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM skills
                WHERE character_id = ?
                ORDER BY sort_order ASC, id ASC
                """,
                (character_id,),
            ).fetchall()
        ]

        palettes = [
            dict(row)
            for row in conn.execute(
                """
                SELECT *
                FROM chat_palettes
                WHERE character_id = ?
                ORDER BY sort_order ASC, id ASC
                """,
                (character_id,),
            ).fetchall()
        ]

        source_values = _source_values(conn, character_id)

    return {
        "derived": derived,
        "skills": skills,
        "palettes": palettes,
        "source_values": source_values,
    }


def save_advanced_bundle(
    character_id: str,
    derived: list[dict],
    skills: list[dict],
    palettes: list[dict],
) -> None:
    with get_connection() as conn:
        _ensure_skill_schema(conn)
        source_values = _source_values(conn, character_id)

        conn.execute(
            "DELETE FROM derived_values WHERE character_id = ?",
            (character_id,),
        )

        for index, row in enumerate(derived):
            label = str(row.get("label", "")).strip()
            formula = str(row.get("formula", "")).strip()

            if not label and not formula:
                continue
            if not label:
                raise ValueError("派生値の名前が空の行があります。")

            result = ""
            error = ""

            if formula:
                try:
                    result = evaluate_formula(formula, source_values)
                except FormulaError as exc:
                    error = str(exc)

            conn.execute(
                """
                INSERT INTO derived_values(
                    id,
                    character_id,
                    label,
                    formula,
                    last_value,
                    error,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_app_id(),
                    character_id,
                    label,
                    formula,
                    result,
                    error,
                    index,
                ),
            )

        conn.execute(
            "DELETE FROM skills WHERE character_id = ?",
            (character_id,),
        )

        for index, row in enumerate(skills):
            label = str(row.get("label", "")).strip()
            value = str(row.get("value", "")).strip()
            category = str(row.get("category", "")).strip()

            if not label and not value:
                continue
            if not label:
                raise ValueError("技能名が空の行があります。")

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
                    index,
                ),
            )

        conn.execute(
            "DELETE FROM chat_palettes WHERE character_id = ?",
            (character_id,),
        )

        for index, row in enumerate(palettes):
            name = str(row.get("name", "")).strip()
            mode = str(row.get("mode", "normal")).strip()
            content = str(row.get("content", ""))

            if not name and not content.strip():
                continue

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
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_app_id(),
                    character_id,
                    name or "チャットパレット",
                    mode or "normal",
                    content,
                    index,
                ),
            )


def _insert_missing_param(conn, character_id: str, label: str):
    exists = conn.execute(
        """
        SELECT 1
        FROM params
        WHERE character_id = ?
          AND label = ?
        LIMIT 1
        """,
        (character_id, label),
    ).fetchone()

    if exists:
        return

    next_order = conn.execute(
        """
        SELECT COALESCE(MAX(sort_order), -1) + 1 AS n
        FROM params
        WHERE character_id = ?
        """,
        (character_id,),
    ).fetchone()["n"]

    conn.execute(
        """
        INSERT INTO params(
            id,
            character_id,
            label,
            value,
            sort_order
        )
        VALUES (?, ?, ?, '', ?)
        """,
        (generate_app_id(), character_id, label, next_order),
    )


def _derived_result(source_values: dict[str, object], formula: str):
    try:
        text = evaluate_formula(formula, source_values)
    except FormulaError:
        return None

    try:
        return float(text)
    except ValueError:
        return None


def _insert_missing_status(
    conn,
    character_id: str,
    label: str,
    current_value,
    max_value,
):
    exists = conn.execute(
        """
        SELECT 1
        FROM statuses
        WHERE character_id = ?
          AND label = ?
        LIMIT 1
        """,
        (character_id, label),
    ).fetchone()

    if exists:
        return

    next_order = conn.execute(
        """
        SELECT COALESCE(MAX(sort_order), -1) + 1 AS n
        FROM statuses
        WHERE character_id = ?
        """,
        (character_id,),
    ).fetchone()["n"]

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
            label,
            current_value,
            max_value,
            next_order,
        ),
    )


def apply_coc6_template(character_id: str) -> None:
    with get_connection() as conn:
        _ensure_skill_schema(conn)

        for label in COC6_PARAMS:
            _insert_missing_param(conn, character_id, label)

        source_values = _source_values(conn, character_id)

        hp = _derived_result(source_values, "ceil(([CON]+[SIZ])/2)")
        mp = _derived_result(source_values, "[POW]")
        san = _derived_result(source_values, "[POW]*5")

        _insert_missing_status(conn, character_id, "HP", hp, hp)
        _insert_missing_status(conn, character_id, "MP", mp, mp)
        _insert_missing_status(conn, character_id, "SAN", san, 99)

        existing_derived = {
            row["label"]
            for row in conn.execute(
                "SELECT label FROM derived_values WHERE character_id = ?",
                (character_id,),
            )
        }

        next_order = conn.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) + 1 AS n
            FROM derived_values
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()["n"]

        source_values = _source_values(conn, character_id)

        for label, formula in COC6_DERIVED:
            if label in existing_derived:
                continue

            result = ""
            error = ""

            try:
                result = evaluate_formula(formula, source_values)
            except FormulaError as exc:
                error = str(exc)

            conn.execute(
                """
                INSERT INTO derived_values(
                    id,
                    character_id,
                    label,
                    formula,
                    last_value,
                    error,
                    sort_order
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    generate_app_id(),
                    character_id,
                    label,
                    formula,
                    result,
                    error,
                    next_order,
                ),
            )
            next_order += 1

        existing_rows = conn.execute(
            """
            SELECT id, label, category
            FROM skills
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchall()

        existing_by_label = {row["label"]: row for row in existing_rows}

        next_skill_order = conn.execute(
            """
            SELECT COALESCE(MAX(sort_order), -1) + 1 AS n
            FROM skills
            WHERE character_id = ?
            """,
            (character_id,),
        ).fetchone()["n"]

        for label, value, category in COC6_SKILLS:
            existing = existing_by_label.get(label)

            if existing is not None:
                if not str(existing["category"] or "").strip():
                    conn.execute(
                        "UPDATE skills SET category = ? WHERE id = ?",
                        (category, existing["id"]),
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
                    next_skill_order,
                ),
            )
            next_skill_order += 1


def generate_coc6_palette(character_id: str) -> str:
    with get_connection() as conn:
        _ensure_skill_schema(conn)
        source_values = _source_values(conn, character_id)

        derived_rows = conn.execute(
            """
            SELECT label, formula
            FROM derived_values
            WHERE character_id = ?
            ORDER BY sort_order ASC
            """,
            (character_id,),
        ).fetchall()

        skill_rows = conn.execute(
            """
            SELECT label, value
            FROM skills
            WHERE character_id = ?
            ORDER BY sort_order ASC
            """,
            (character_id,),
        ).fetchall()

    resolved_derived = {}
    for row in derived_rows:
        try:
            resolved_derived[row["label"]] = evaluate_formula(
                row["formula"],
                source_values,
            )
        except FormulaError:
            pass

    lines = []

    for label in ("SAN", "アイデア", "幸運", "知識"):
        value = resolved_derived.get(label)
        if value:
            lines.append(f"CCB<={value} {label}")

    if lines:
        lines.append("")

    for row in skill_rows:
        result, error = resolve_value_text(row["value"], source_values)
        if result and not error:
            lines.append(f"CCB<={result} {row['label']}")

    return "\n".join(lines).strip()
