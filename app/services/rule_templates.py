from __future__ import annotations


RULE_TEMPLATES = {
    "generic": {
        "id": "generic",
        "name": "汎用",
        "params": [],
        "statuses": [],
    },
    "coc6": {
        "id": "coc6",
        "name": "CoC6",
        "params": [
            {"label": "STR"},
            {"label": "CON"},
            {"label": "POW"},
            {"label": "DEX"},
            {"label": "APP"},
            {"label": "SIZ"},
            {"label": "INT"},
            {"label": "EDU"},
            {
                "label": "アイデア",
                "formula": "[INT]*5",
            },
            {
                "label": "幸運",
                "formula": "[POW]*5",
            },
            {
                "label": "知識",
                "formula": "[EDU]*5",
            },
            {
                "label": "DB",
                "formula": "db6([STR]+[SIZ])",
            },
            {
                "label": "職業技能P",
                "formula": "[EDU]*20",
            },
            {
                "label": "趣味技能P",
                "formula": "[INT]*10",
            },
        ],
        "statuses": [
            {
                "label": "HP",
                "initial_formula": "ceil(([CON]+[SIZ])/2)",
                "max_formula": "ceil(([CON]+[SIZ])/2)",
            },
            {
                "label": "MP",
                "initial_formula": "[POW]",
                "max_formula": "[POW]",
            },
            {
                "label": "SAN",
                "initial_formula": "[POW]*5",
                "max_value": 99,
            },
        ],
    },
}


def get_rule_template(
    template_id: str,
):
    return RULE_TEMPLATES.get(
        template_id
    )


def list_rule_templates():
    return [
        {
            "id": data["id"],
            "name": data["name"],
        }
        for data in RULE_TEMPLATES.values()
    ]
