import os
import time
import re
import hashlib
from collections import Counter
from backend.llm_client import analyze_code_with_llm
from backend.db import save_scan
from backend.scoring import compute_file_weight, score_file, score_project


def calculate_complexity(code: str) -> dict:
    keywords = ["if ", "else", "for ", "while ", "catch ", "case ", "&&", "||", "?:"]
    score = 1
    for kw in keywords:
        score += code.count(kw)

    # Bug fix #5: the original code used '\\n' (a two-character literal backslash-n)
    # instead of '\n', so split() never split anything and every file reported 1 LOC.
    # Using splitlines() is the most robust cross-platform fix.
    lines = len(code.splitlines()) or 1
    comments = len(re.findall(r'(//|#|/\*)', code))
    comment_ratio = round(comments / lines, 2) if lines > 0 else 0

    return {
        "cyclomatic_estimation": score,
        "loc": lines,
        "comment_ratio": comment_ratio,
    }


# File extensions we care about for the target languages
LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".java": "Java",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".ts": "JavaScript",  # include TS under JS codebase loosely
    ".tsx": "JavaScript",
}

IGNORE_DIRS = {"node_modules", "venv", ".git", "__pycache__", "dist", "build"}


def detect_language(directory: str) -> str:
    ext_counter = Counter()
    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in LANGUAGE_EXTENSIONS:
                ext_counter[LANGUAGE_EXTENSIONS[ext]] += 1

    if not ext_counter:
        return "Unknown"

    return ext_counter.most_common(1)[0][0]


def analyze_directory(directory: str, project_id: str, sensitivity: str) -> dict:
    start_time = time.time()
    language = detect_language(directory)

    if language == "Unknown":
        language = "JavaScript"  # fallback

    results = {}
    file_results = []
    all_smells = []

    def make_smell_id(file_rel_path: str, smell: dict) -> str:
        # Stable identifier so the backend can persist user acceptance across UI reloads.
        base = "|".join(
            [
                str(project_id),
                str(file_rel_path),
                str(smell.get("name", "")),
                str(smell.get("line_start", "")),
                str(smell.get("line_end", "")),
                str(smell.get("category", "")),
                str(smell.get("severity", "")),
            ]
        )
        return hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]

    for root, dirs, files in os.walk(directory):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in LANGUAGE_EXTENSIONS and LANGUAGE_EXTENSIONS[ext] == language:
                filepath = os.path.join(root, f)
                rel_path = os.path.relpath(filepath, directory)

                try:
                    with open(filepath, "r", encoding="utf-8") as file_obj:
                        code = file_obj.read()

                    # Skip extremely large files
                    if len(code) > 100000:
                        continue

                    metrics = calculate_complexity(code)
                    analysis = analyze_code_with_llm(code, rel_path, language, sensitivity, metrics)

                    smells = analysis.get("smells", []) or []
                    # Normalize required fields so UI rendering is consistent.
                    for smell in smells:
                        smell["file"] = rel_path
                        smell["smell_id"] = make_smell_id(rel_path, smell)
                        smell.setdefault("line_start", 0)
                        smell.setdefault("line_end", 0)
                        smell.setdefault("category", "")
                        smell.setdefault("severity", "medium")

                    file_score, _breakdown = score_file(smells, metrics, sensitivity)
                    weight = compute_file_weight(metrics)
                    file_results.append({"file_score": file_score, "weight": weight})

                    results[rel_path] = {
                        "score": file_score,
                        "smells": smells,
                    }

                    all_smells.extend(smells)

                except Exception as e:
                    print(f"Failed to read or analyze {filepath}: {e}")

    overall_score = score_project(file_results)
    scan_time = time.time() - start_time

    details = {
        "language": language,
        "files": results,
        "all_smells": all_smells,
        "scan_time": scan_time,
        "files_scanned": len(file_results),
    }

    scan_id = save_scan(project_id, overall_score, sensitivity, details)
    return {
        "project_id": project_id,
        "scan_id": scan_id,
        "overall_score": overall_score,
        "details": details,
    }
