from __future__ import annotations

import ast
import math
import operator
import re
from typing import Any


REFERENCE_PATTERN = re.compile(
    r"\[([^\[\]]+)\]"
)


class FormulaError(ValueError):
    pass


def _db6(value: float):
    value = float(value)

    if value <= 1:
        return "-2D6"
    if value <= 12:
        return "-1D6"
    if value <= 16:
        return "0"
    if value <= 24:
        return "+1D4"
    if value <= 32:
        return "+1D6"

    extra = int(
        math.ceil(
            (value - 32) / 16
        )
    )

    dice = 1 + extra
    return f"+{dice}D6"


FUNCTIONS = {
    "ceil": math.ceil,
    "floor": math.floor,
    "round": round,
    "db6": _db6,
}

BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}

UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


def _coerce_number(
    value: Any,
):
    if isinstance(
        value,
        bool,
    ):
        raise FormulaError(
            "真偽値は数値として扱えません。"
        )

    if isinstance(
        value,
        (
            int,
            float,
        ),
    ):
        return value

    text = str(
        value
    ).strip()

    if not text:
        raise FormulaError(
            "参照値が空です。"
        )

    try:
        number = float(
            text
        )
    except ValueError as exc:
        raise FormulaError(
            f"数値ではない値を参照しています: {text}"
        ) from exc

    if number.is_integer():
        return int(
            number
        )

    return number


def _eval_node(
    node,
    refs,
):
    if isinstance(
        node,
        ast.Expression,
    ):
        return _eval_node(
            node.body,
            refs,
        )

    if isinstance(
        node,
        ast.Constant,
    ):
        if isinstance(
            node.value,
            (
                int,
                float,
            ),
        ):
            return node.value

        raise FormulaError(
            "数値以外の定数は使えません。"
        )

    if isinstance(
        node,
        ast.Name,
    ):
        if node.id.startswith(
            "__ref_"
        ):
            try:
                index = int(
                    node.id[6:]
                )
            except ValueError as exc:
                raise FormulaError(
                    "参照式が不正です。"
                ) from exc

            if not (
                0
                <= index
                < len(refs)
            ):
                raise FormulaError(
                    "参照式が不正です。"
                )

            return _coerce_number(
                refs[index]
            )

        raise FormulaError(
            f"使用できない名前です: {node.id}"
        )

    if isinstance(
        node,
        ast.BinOp,
    ):
        op_type = type(
            node.op
        )

        if op_type not in BIN_OPS:
            raise FormulaError(
                "使用できない演算子です。"
            )

        left = _eval_node(
            node.left,
            refs,
        )
        right = _eval_node(
            node.right,
            refs,
        )

        if not isinstance(
            left,
            (
                int,
                float,
            ),
        ) or not isinstance(
            right,
            (
                int,
                float,
            ),
        ):
            raise FormulaError(
                "文字列結果に算術演算はできません。"
            )

        try:
            return BIN_OPS[
                op_type
            ](
                left,
                right,
            )
        except Exception as exc:
            raise FormulaError(
                str(
                    exc
                )
            ) from exc

    if isinstance(
        node,
        ast.UnaryOp,
    ):
        op_type = type(
            node.op
        )

        if op_type not in UNARY_OPS:
            raise FormulaError(
                "使用できない単項演算子です。"
            )

        value = _eval_node(
            node.operand,
            refs,
        )

        if not isinstance(
            value,
            (
                int,
                float,
            ),
        ):
            raise FormulaError(
                "文字列結果には使えません。"
            )

        return UNARY_OPS[
            op_type
        ](
            value
        )

    if isinstance(
        node,
        ast.Call,
    ):
        if not (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            in FUNCTIONS
        ):
            raise FormulaError(
                "使用できない関数です。"
            )

        if node.keywords:
            raise FormulaError(
                "キーワード引数は使えません。"
            )

        args = [
            _eval_node(
                arg,
                refs,
            )
            for arg in node.args
        ]

        try:
            return FUNCTIONS[
                node.func.id
            ](
                *args
            )
        except Exception as exc:
            raise FormulaError(
                str(
                    exc
                )
            ) from exc

    raise FormulaError(
        "使用できない式です。"
    )


def evaluate_formula(
    formula: str,
    values: dict[str, Any],
):
    expression = str(
        formula
        or ""
    ).strip()

    if not expression:
        raise FormulaError(
            "式が空です。"
        )

    refs = []

    def replace_reference(
        match,
    ):
        label = match.group(
            1
        ).strip()

        if label not in values:
            raise FormulaError(
                f"参照先がありません: {label}"
            )

        refs.append(
            values[label]
        )

        return (
            f"__ref_{len(refs) - 1}"
        )

    try:
        expression = (
            REFERENCE_PATTERN.sub(
                replace_reference,
                expression,
            )
        )
    except FormulaError:
        raise

    try:
        tree = ast.parse(
            expression,
            mode="eval",
        )
    except SyntaxError as exc:
        raise FormulaError(
            "式の構文が不正です。"
        ) from exc

    return _eval_node(
        tree,
        refs,
    )


def format_formula_value(
    value,
):
    if isinstance(
        value,
        float,
    ):
        if value.is_integer():
            return str(
                int(
                    value
                )
            )

        return str(
            round(
                value,
                8,
            )
        )

    return str(
        value
    )
