import os

from backend.utils import detect_language, read_file_safe
from backend.llm_client import analyze_code_with_llm
from backend.scoring import compute_file_weight, score_file, score_project
from backend.db import save_scan

def calculate_metrics(code):

    lines = code.splitlines()

    loc = len(lines)

    comment_lines = [
        l for l in lines
        if l.strip().startswith("#")
        or l.strip().startswith("//")
    ]

    comment_ratio = (
        len(comment_lines) / loc
        if loc > 0 else 0
    )

    complexity_estimation = code.count("if") + code.count("for")

    return {
        "loc": loc,
        "comment_ratio": comment_ratio,
        "cyclomatic_estimation": complexity_estimation
    }


def analyze_directory(root_dir):

    file_results = []

    all_smells = []

    for root, _, files in os.walk(root_dir):

        for file in files:

            language = detect_language(file)

            if not language:
                continue

            path = os.path.join(root, file)

            code = read_file_safe(path)

            metrics = calculate_metrics(code)

            print(f"Analyzing: {file}")

            analysis = analyze_code_with_llm(
                code,
                file,
                language,
                "balanced",
                metrics
            )

            smells = analysis.get("smells", [])

            weight = compute_file_weight(metrics)

            file_score = score_file(smells)

            file_result = {
    "file": file,
    "metrics": metrics,
    "file_score": file_score,
    "weight": weight,
    "smells": smells
}

            file_results.append(file_result)

            all_smells.extend(smells)

    overall_score = score_project(file_results)

    save_scan(overall_score)

    return {
        "overall_score": overall_score,
        "files": file_results,
        "all_smells": all_smells
    }