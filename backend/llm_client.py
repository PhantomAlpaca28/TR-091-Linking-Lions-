try:
    from backend.snippets import (
        excerpt_lines,
        first_branch_line_heuristic,
        first_line_containing,
        first_long_line_index,
        line_of_max_indent,
        split_lines,
    )
except ModuleNotFoundError:
    from snippets import (
        excerpt_lines,
        first_branch_line_heuristic,
        first_line_containing,
        first_long_line_index,
        line_of_max_indent,
        split_lines,
    )


def analyze_code_with_llm(
    code,
    filename,
    language,
    sensitivity,
    metrics,
):

    smells = []
    level = (sensitivity or "balanced").lower()
    if level not in {"strict", "balanced", "lenient"}:
        level = "balanced"
    threshold_by_level = {
        "strict": {"indent": 16, "long_file": 160, "cc_major": 45, "cc_med": 28, "cc_minor": 18, "avg_line_len": 105},
        "balanced": {"indent": 20, "long_file": 200, "cc_major": 55, "cc_med": 35, "cc_minor": 22, "avg_line_len": 120},
        "lenient": {"indent": 24, "long_file": 260, "cc_major": 65, "cc_med": 42, "cc_minor": 28, "avg_line_len": 132},
    }
    t = threshold_by_level[level]
    lines = split_lines(code)
    physical_lines = len(lines)

    indent_levels = [
        len(line) - len(line.lstrip())
        for line in lines
        if line.strip()
    ]

    if indent_levels and max(indent_levels) > t["indent"]:
        ref_line = line_of_max_indent(lines) or 1
        start = max(1, ref_line - 2)
        end = min(physical_lines, ref_line + 2)
        before = excerpt_lines(lines, start, end, max_lines=8)
        smells.append({
            "catalog_id": "deep_nesting",
            "name": "Deep Nesting",
            "severity": "major",
            "explanation": "Too many nested blocks make code hard to read.",
            "suggestion": "Move nested logic into separate functions or early-return to flatten structure.",
            "line_start": start,
            "line_end": end,
            "line_reference": f"L{start}–L{end}",
            "before": before,
            "after": "# Example: extract inner block into a named function and call it here.",
        })

    if physical_lines > t["long_file"]:
        start, end = 1, min(physical_lines, 15)
        before = excerpt_lines(lines, start, end, max_lines=15)
        smells.append({
            "catalog_id": "long_file",
            "name": "Long File",
            "severity": "medium",
            "explanation": "File is very long for a single module.",
            "suggestion": "Split into smaller modules or extract cohesive units (types, helpers, feature slices).",
            "line_start": start,
            "line_end": end,
            "line_reference": f"L{start}–L{end} (file head)",
            "before": before,
            "after": f"# Split into multiple files; aim for <200–300 lines per unit where practical.\n# e.g. {filename} → components/ + lib/ + types/",
        })

    if "TODO" in code:
        ln = first_line_containing(lines, "TODO") or 1
        start = max(1, ln - 1)
        end = min(physical_lines, ln + 1)
        before = excerpt_lines(lines, start, end, max_lines=5)
        smells.append({
            "catalog_id": "todo_comment",
            "name": "TODO Comment",
            "severity": "minor",
            "explanation": "Unfinished TODO found.",
            "suggestion": "Complete the work, create a tracked issue with acceptance criteria, or remove stale TODOs.",
            "line_start": ln,
            "line_end": ln,
            "line_reference": f"L{ln}",
            "before": before,
            "after": before.replace("TODO", "DONE", 1) if "TODO" in before else "# Resolved: implementation complete.",
        })

    for marker, catalog_id, label in (
        ("FIXME", "fixme_comment", "FIXME Comment"),
        ("HACK", "hack_comment", "HACK Comment"),
    ):
        if marker in code:
            ln = first_line_containing(lines, marker) or 1
            start = max(1, ln - 1)
            end = min(physical_lines, ln + 1)
            before = excerpt_lines(lines, start, end, max_lines=5)
            smells.append({
                "catalog_id": catalog_id,
                "name": label,
                "severity": "minor",
                "explanation": f"Found {marker} marker indicating tech debt.",
                "suggestion": "Track in backlog, add tests around the risky area, or replace with a maintainable approach.",
                "line_start": ln,
                "line_end": ln,
                "line_reference": f"L{ln}",
                "before": before,
                "after": "# Replace hack with documented behavior + tests; link issue ID in comment.",
            })

    cc = metrics.get("cyclomatic_complexity", metrics.get("cyclomatic_estimation", 1))

    if cc >= t["cc_major"]:
        ref_line = first_branch_line_heuristic(lines) or 1
        start = max(1, ref_line - 1)
        end = min(physical_lines, ref_line + 4)
        before = excerpt_lines(lines, start, end, max_lines=10)
        smells.append({
            "catalog_id": "cyclomatic_high",
            "name": "High Cyclomatic Complexity",
            "severity": "major",
            "explanation": f"Estimated cyclomatic complexity is very high (~{cc}), indicating many branches and paths.",
            "suggestion": "Refactor: extract functions per branch cluster, replace flags with polymorphism or lookup tables.",
            "line_start": start,
            "line_end": end,
            "line_reference": f"L{start}–L{end}",
            "before": before,
            "after": "# Example: extract is_valid_* helpers; replace nested if/else with guard clauses.",
        })
    elif cc >= t["cc_med"]:
        ref_line = first_branch_line_heuristic(lines) or 1
        start = max(1, ref_line - 1)
        end = min(physical_lines, ref_line + 3)
        before = excerpt_lines(lines, start, end, max_lines=8)
        smells.append({
            "catalog_id": "cyclomatic_elevated",
            "name": "Elevated Cyclomatic Complexity",
            "severity": "medium",
            "explanation": f"Estimated cyclomatic complexity is elevated (~{cc}).",
            "suggestion": "Split logic into smaller functions; document decision points.",
            "line_start": start,
            "line_end": end,
            "line_reference": f"L{start}–L{end}",
            "before": before,
            "after": "# Example: break into step1(), step2() with explicit data transfer object.",
        })
    elif cc >= t["cc_minor"]:
        ref_line = first_branch_line_heuristic(lines) or 1
        start = max(1, ref_line)
        end = min(physical_lines, ref_line + 2)
        before = excerpt_lines(lines, start, end, max_lines=6)
        smells.append({
            "catalog_id": "cyclomatic_moderate",
            "name": "Moderate Cyclomatic Complexity",
            "severity": "minor",
            "explanation": f"Estimated cyclomatic complexity is moderate (~{cc}).",
            "suggestion": "Consider simplifying as the file grows; add tests around branching.",
            "line_start": start,
            "line_end": end,
            "line_reference": f"L{start}–L{end}",
            "before": before,
            "after": "# Keep an eye on growth; prefer small helpers over growing this block.",
        })

    avg_line_len = sum(len(line) for line in lines) / max(physical_lines, 1)
    if avg_line_len > t["avg_line_len"] and physical_lines > 30:
        ln = first_long_line_index(lines, t["avg_line_len"]) or 1
        start = max(1, ln)
        end = min(physical_lines, ln)
        before = f"L{ln}: {lines[ln - 1]}" if 1 <= ln <= physical_lines else f"L{ln}:"
        smells.append({
            "catalog_id": "long_lines",
            "name": "Long Lines",
            "severity": "minor",
            "explanation": "Many lines are very long, hurting readability.",
            "suggestion": "Wrap at ~100 columns, extract expressions into named locals.",
            "line_start": ln,
            "line_end": ln,
            "line_reference": f"L{ln}",
            "before": before[:500] + ("…" if len(before) > 500 else ""),
            "after": "# Break into multiple lines with intermediate variables for clarity.",
        })

    return {"smells": smells}
