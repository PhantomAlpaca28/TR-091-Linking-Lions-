"""Static smell catalog and evaluation methodology exposed to the API."""

SMELL_CATALOG = [
    {
        "catalog_id": "deep_nesting",
        "name": "Deep Nesting",
        "category": "Maintainability",
        "description": "Excessive indentation depth suggests tangled control flow and harder reasoning about behavior.",
    },
    {
        "catalog_id": "long_file",
        "name": "Long File",
        "category": "Size",
        "description": "Very large files often mix responsibilities and resist navigation and review.",
    },
    {
        "catalog_id": "todo_comment",
        "name": "TODO Comment",
        "category": "Process",
        "description": "Outstanding TODO markers indicate deferred work or unclear completion criteria.",
    },
    {
        "catalog_id": "fixme_comment",
        "name": "FIXME Comment",
        "category": "Process",
        "description": "FIXME markers usually signal known defects or risky areas.",
    },
    {
        "catalog_id": "hack_comment",
        "name": "HACK Comment",
        "category": "Process",
        "description": "HACK markers imply brittle or temporary solutions that may not hold under change.",
    },
    {
        "catalog_id": "cyclomatic_high",
        "name": "High Cyclomatic Complexity",
        "category": "Complexity",
        "description": "Many independent paths through a unit increase testing burden and defect risk.",
    },
    {
        "catalog_id": "cyclomatic_elevated",
        "name": "Elevated Cyclomatic Complexity",
        "category": "Complexity",
        "description": "Elevated branching suggests opportunities to decompose or clarify logic.",
    },
    {
        "catalog_id": "cyclomatic_moderate",
        "name": "Moderate Cyclomatic Complexity",
        "category": "Complexity",
        "description": "Moderate complexity is acceptable but worth monitoring as the file grows.",
    },
    {
        "catalog_id": "long_lines",
        "name": "Long Lines",
        "category": "Readability",
        "description": "Overlong lines reduce scanability and complicate diffs and reviews.",
    },
]


EVALUATION_METRICS = [
    {
        "id": "sonar_precision",
        "title": "Code smell detection precision vs. SonarQube baseline",
        "description":
            "Reported smells are benchmarked against a SonarQube ruleset on representative corpora; precision and recall "
            "targets are tracked release-over-release.",
    },
    {
        "id": "acceptance_rate",
        "title": "Refactoring suggestion acceptance rate (human-rated)",
        "description":
            "Blind reviews score suggested after snippets for usefulness; acceptance rate guides prompt and heuristic tuning.",
    },
    {
        "id": "scan_latency",
        "title": "Scan completion time for 10k-line codebase",
        "description":
            "End-to-end scan duration on a standardized ~10k LOC tree (excluding vendor) is measured in CI for regressions.",
    },
]


def get_smell_catalog():
    return list(SMELL_CATALOG)


def get_evaluation_metrics():
    return list(EVALUATION_METRICS)
