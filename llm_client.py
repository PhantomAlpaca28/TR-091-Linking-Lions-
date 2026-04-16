def simple_rule_analysis(code):

    smells = []

    lines = code.splitlines()

    # Deep nesting detection
    indent_levels = [
        len(line) - len(line.lstrip())
        for line in lines
        if line.strip()
    ]

    if indent_levels and max(indent_levels) > 20:

        smells.append({
            "name": "Deep Nesting",
            "severity": "major",

            "explanation":
            "Code has too many nested blocks which reduces readability.",

            "suggestion":
            "Refactor nested loops into separate functions.",

            "before":
            "for i:\n  for j:\n    for k:\n      ...",

            "after":
            "def process():\n  ...\n\nfor i:\n  process()"
        })

    # Long method
    if len(lines) > 200:

        smells.append({
            "name": "Long Method",
            "severity": "medium",

            "explanation":
            "Function contains too many lines making it hard to maintain.",

            "suggestion":
            "Break function into smaller reusable functions.",

            "before":
            "def big_function():\n   many lines...",

            "after":
            "def small_function():\n   ..."
        })

    # TODO detection
    if "TODO" in code:

        smells.append({
            "name": "TODO Comment",
            "severity": "minor",

            "explanation":
            "Unfinished TODO comment found.",

            "suggestion":
            "Complete or remove TODO comment.",

            "before":
            "# TODO fix",

            "after":
            "# Completed"
        })

    return {"smells": smells}


def analyze_code_with_llm(
    code,
    filename,
    language,
    sensitivity,
    metrics
):

    return simple_rule_analysis(code)