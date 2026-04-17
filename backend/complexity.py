"""Language-agnostic cyclomatic complexity estimation (McCabe-style, file-level)."""

import re


def estimate_cyclomatic_complexity(code: str) -> int:
    """
    Approximate cyclomatic complexity for a source file without parsing an AST.
    Starts at 1 (single path) and adds one for each decision / branch keyword
    and common logical operators in C-style and Python code.
    """
    if not code or not code.strip():
        return 1

    text = code

    # Decision and branch constructs (word-boundary safe).
    patterns = [
        r"\bif\b",
        r"\belif\b",
        r"\belse\s+if\b",
        r"\bfor\b",
        r"\bwhile\b",
        r"\bdo\b",
        r"\bswitch\b",
        r"\bcase\b",
        r"\bdefault\b",
        r"\bcatch\b",
        r"\bexcept\b",
        r"\bfinally\b",
    ]

    count = 1
    for pat in patterns:
        count += len(re.findall(pat, text, re.IGNORECASE))

    # Logical operators (extra paths in C-style / JS / Java).
    count += text.count("&&")
    count += text.count("||")

    return max(1, count)
