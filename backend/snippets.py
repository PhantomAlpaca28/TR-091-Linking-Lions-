"""Extract line numbers and code excerpts for smell reporting."""

import re

_BRANCH_LINE = re.compile(
    r"^\s*(if|for|while|switch|case|catch)\b",
    re.IGNORECASE,
)


def split_lines(code: str) -> list[str]:
    return code.splitlines()


def excerpt_lines(
    lines: list[str],
    start_1: int,
    end_1: int,
    max_lines: int = 12,
    *,
    with_line_numbers: bool = True,
) -> str:
    """1-based inclusive line range, clamped; returns joined excerpt.

    By default, prefixes each line with its original file line number (e.g. `L42: ...`)
    so users can jump straight to the source.
    """
    if not lines:
        return ""
    n = len(lines)
    start_1 = max(1, min(start_1, n))
    end_1 = max(start_1, min(end_1, n))
    span = end_1 - start_1 + 1
    if span > max_lines:
        end_1 = start_1 + max_lines - 1
    chunk = lines[start_1 - 1 : end_1]
    if not with_line_numbers:
        return "\n".join(chunk)
    return "\n".join(f"L{start_1 + i}: {line}" for i, line in enumerate(chunk))


def first_line_matching(lines: list[str], predicate) -> int | None:
    for i, line in enumerate(lines, start=1):
        if predicate(line):
            return i
    return None


def line_of_max_indent(lines: list[str]) -> int | None:
    best_i = None
    best_indent = -1
    for i, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent > best_indent:
            best_indent = indent
            best_i = i
    return best_i


def first_line_containing(lines: list[str], needle: str) -> int | None:
    needle_lower = needle.lower()
    for i, line in enumerate(lines, start=1):
        if needle_lower in line.lower():
            return i
    return None


def first_long_line_index(lines: list[str], min_len: int) -> int | None:
    for i, line in enumerate(lines, start=1):
        if len(line) >= min_len:
            return i
    return None


def first_branch_line_heuristic(lines: list[str]) -> int | None:
    for i, line in enumerate(lines, start=1):
        if _BRANCH_LINE.search(line):
            return i
    return None
