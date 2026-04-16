def compute_file_weight(metrics):

    loc = metrics["loc"]

    return max(1, loc // 100)


def score_file(smells):

    penalty = 0

    for smell in smells:

        severity = smell.get("severity", "medium")

        if severity == "major":
            penalty += 10

        elif severity == "medium":
            penalty += 5

        else:
            penalty += 2

    score = max(0, 100 - penalty)

    return score


def score_project(file_results):

    if not file_results:
        return 100

    total = 0
    weights = 0

    for fr in file_results:

        total += fr["file_score"] * fr["weight"]

        weights += fr["weight"]

    return int(total / weights)