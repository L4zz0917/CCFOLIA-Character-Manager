from __future__ import annotations

import ast
import math
import operator
import re


REFERENCE_RE = re.compile(r"\[([^\[\]]+)\]")

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


def _damage_bonus_6e(value):
    value = float(value)

    if value <= 12:
        return "-1D6"
    if value <= 16:
        return "-1D4"
    if value <= 24:
        return "0"
    if value <= 32:
        return "+1D4"
    if value <= 40:
        return "+1D6"

    dice = 2 + max(0, math.ceil((value - 56) / 16))
    return f"+{dice}D6"


FUNCTIONS = {
    "ceil": math.ceil,
    "floor": math.floor,
    "round": round,
    "db6": _damage_bonus_6e,
}


class FormulaError(ValueError):
    pass


def _to_number(value, label: str):
    if value is None:
        raise FormulaError(f"「{label}」が未入力です。")

    if isinstance(value, str):
        value = value.strip()
        if not value:
            raise FormulaError(f"「{label}」が未入力です。")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise FormulaError(
            f"「{label}」は数値として参照できません。"
        ) from exc

    if not math.isfinite(number):
        raise FormulaError(
            f"「{label}」は有限の数値ではありません。"
        )

    return number


def _eval_node(node, variables):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, variables)

    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            raise FormulaError("真偽値は使用できません。")
        if isinstance(node.value, (int, float)):
            return node.value
        raise FormulaError("文字列定数は使用できません。")

    if isinstance(node, ast.Name):
        if node.id not in variables:
            raise FormulaError("未定義の値があります。")
        return variables[node.id]

    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in BIN_OPS:
            raise FormulaError("この演算子は使用できません。")

        left = _eval_node(node.left, variables)
        right = _eval_node(node.right, variables)

        try:
            return BIN_OPS[op_type](left, right)
        except ZeroDivisionError as exc:
            raise FormulaError("0では割れません。") from exc

    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in UNARY_OPS:
            raise FormulaError("この単項演算子は使用できません。")
        return UNARY_OPS[op_type](
            _eval_node(node.operand, variables)
        )

    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise FormulaError("この関数呼び出しは使用できません。")

        name = node.func.id
        if name not in FUNCTIONS:
            raise FormulaError(
                f"関数「{name}」は使用できません。"
            )

        if node.keywords:
            raise FormulaError(
                "キーワード引数は使用できません。"
            )

        args = [
            _eval_node(arg, variables)
            for arg in node.args
        ]

        try:
            return FUNCTIONS[name](*args)
        except Exception as exc:
            raise FormulaError(
                f"関数「{name}」の計算に失敗しました。"
            ) from exc

    raise FormulaError("この式は使用できません。")


def format_result(value) -> str:
    if isinstance(value, float):
        if not math.isfinite(value):
            raise FormulaError(
                "計算結果が有限の数値ではありません。"
            )
        if value.is_integer():
            return str(int(value))
        return f"{value:.10g}"

    return str(value)


def evaluate_formula(
    formula: str,
    source_values: dict[str, object],
) -> str:
    formula = str(formula).strip()

    if not formula:
        return ""

    variables = {}
    transformed = formula

    refs = REFERENCE_RE.findall(formula)

    for index, raw_label in enumerate(refs):
        label = raw_label.strip()
        key = f"__v{index}"

        if label not in source_values:
            raise FormulaError(
                f"参照先「{label}」が見つかりません。"
            )

        variables[key] = _to_number(
            source_values[label],
            label,
        )

        transformed = transformed.replace(
            f"[{raw_label}]",
            key,
            1,
        )

    try:
        tree = ast.parse(
            transformed,
            mode="eval",
        )
    except SyntaxError as exc:
        raise FormulaError(
            "式の構文が正しくありません。"
        ) from exc

    result = _eval_node(tree, variables)
    return format_result(result)


def resolve_value_text(
    text: str,
    source_values: dict[str, object],
) -> tuple[str, str]:
    raw = str(text).strip()

    if not raw:
        return "", ""

    try:
        number = float(raw)
        if math.isfinite(number):
            return format_result(number), ""
    except ValueError:
        pass

    try:
        return evaluate_formula(raw, source_values), ""
    except FormulaError as exc:
        return "", str(exc)
