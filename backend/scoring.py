"""Weighted project score and per-file penalties (capped so single files don't collapse to zero)."""

# Many smells on one file shouldn't drive score to 0; cap keeps reports interpretable.
MAX_PENALTY_PER_FILE = 85

SENSITIVITY_WEIGHTS = {
    "strict": {"major": 14, "medium": 7, "minor": 3, "cap": 92},
    "balanced": {"major": 10, "medium": 5, "minor": 2, "cap": 85},
    "lenient": {"major": 7, "medium": 3, "minor": 1, "cap": 75},
}


def compute_file_weight(metrics):

    loc = metrics["loc"]

    return max(1, loc // 100)


def score_file(smells, sensitivity="balanced"):

    penalty = 0

    profile = SENSITIVITY_WEIGHTS.get(sensitivity, SENSITIVITY_WEIGHTS["balanced"])
    for smell in smells:

        severity = smell.get("severity", "medium")

        if severity == "major":
            penalty += profile["major"]
        elif severity == "medium":
            penalty += profile["medium"]
        else:
            penalty += profile["minor"]

    penalty = min(MAX_PENALTY_PER_FILE, profile["cap"], penalty)
    score = max(0, 100 - penalty)

    return score


def score_project(file_results):

    if not file_results:
        return 0

    total = 0
    weights = 0

    for fr in file_results:

        total += fr["file_score"] * fr["weight"]

        weights += fr["weight"]

    return int(total / weights)
