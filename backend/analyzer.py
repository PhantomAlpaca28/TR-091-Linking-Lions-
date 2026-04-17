import os

import time

import uuid

from datetime import datetime, timezone

from pathlib import Path



try:

    from backend.utils import detect_language, read_file_safe, is_probably_binary

    from backend.llm_client import analyze_code_with_llm

    from backend.llm_refine import refine_smells_for_file

    from backend.scoring import compute_file_weight, score_file, score_project

    from backend.complexity import estimate_cyclomatic_complexity

    from backend.catalog import get_evaluation_metrics, get_smell_catalog

    from backend import config

except ModuleNotFoundError:

    from utils import detect_language, read_file_safe, is_probably_binary

    from llm_client import analyze_code_with_llm

    from llm_refine import refine_smells_for_file

    from scoring import compute_file_weight, score_file, score_project

    from complexity import estimate_cyclomatic_complexity

    from catalog import get_evaluation_metrics, get_smell_catalog

    import config





def calculate_metrics(code):



    lines = code.splitlines()



    physical_lines = len(lines)



    loc = len([ln for ln in lines if ln.strip()])



    cyclomatic_complexity = estimate_cyclomatic_complexity(code)



    return {

        "loc": loc,

        "physical_lines": physical_lines,

        "cyclomatic_complexity": cyclomatic_complexity,

        "cyclomatic_estimation": cyclomatic_complexity,

    }





def _should_skip_directory(root: str, skip_dirs: set) -> bool:

    skip_lower = {s.lower() for s in skip_dirs}

    return any(p.lower() in skip_lower for p in Path(root).parts)





def _merge_skip_dirs(skip_dirs) -> set[str]:

    out = set(config.DEFAULT_SKIP_DIR_NAMES)

    if skip_dirs:

        out |= {str(s).strip().lower() for s in skip_dirs if str(s).strip()}

    return out





def analyze_directory(root_dir, skip_dirs=None, sensitivity=None):



    t0 = time.perf_counter()
    chosen_sensitivity = (sensitivity or config.DEFAULT_SENSITIVITY).strip().lower()
    if chosen_sensitivity not in config.ALLOWED_SENSITIVITY:
        chosen_sensitivity = config.DEFAULT_SENSITIVITY

    skip_dirs = _merge_skip_dirs(skip_dirs)

    llm_refine_enabled = bool(os.getenv("OPENAI_API_KEY", "").strip())



    stats = {

        "files_matched_extension": 0,

        "files_analyzed": 0,

        "skipped_over_bytes": 0,

        "skipped_binary": 0,

        "skipped_empty_or_unreadable": 0,

        "skipped_lines_cap": 0,

        "skipped_io_error": 0,

        "truncated_after_file_cap": False,

    }



    candidates: list[tuple[str, str, int]] = []

    for root, _, files in os.walk(root_dir):



        if _should_skip_directory(root, skip_dirs):

            continue



        for file in files:



            language = detect_language(file)



            if not language:

                continue



            path = os.path.join(root, file)



            try:

                size = os.path.getsize(path)

            except OSError:

                stats["skipped_io_error"] += 1

                continue



            candidates.append((path, language, size))



    stats["files_matched_extension"] = len(candidates)

    candidates.sort(key=lambda t: t[0].replace("\\", "/").lower())



    file_results = []

    for path, language, size in candidates:



        if len(file_results) >= config.MAX_FILES_TO_ANALYZE:

            stats["truncated_after_file_cap"] = True

            break



        if size > config.MAX_ANALYZE_FILE_BYTES:

            stats["skipped_over_bytes"] += 1

            continue



        code = read_file_safe(path)



        if not code.strip():

            stats["skipped_empty_or_unreadable"] += 1

            continue



        if len(code) > config.MAX_ANALYZE_FILE_BYTES:

            stats["skipped_over_bytes"] += 1

            continue



        sample = code[:8000]

        if is_probably_binary(sample):

            stats["skipped_binary"] += 1

            continue



        metrics = calculate_metrics(code)



        if metrics["physical_lines"] > config.MAX_PHYSICAL_LINES:

            stats["skipped_lines_cap"] += 1

            continue



        analysis = analyze_code_with_llm(

            code,

            os.path.basename(path),

            language,

            chosen_sensitivity,

            metrics,

        )



        smells = analysis.get("smells", [])



        if llm_refine_enabled:

            smells = refine_smells_for_file(code, language, os.path.basename(path), smells)



        weight = compute_file_weight(metrics)



        file_score = score_file(smells, chosen_sensitivity)



        file_result = {

            "file": os.path.relpath(path, root_dir),

            "language": language,

            "metrics": metrics,

            "file_score": file_score,

            "weight": weight,

            "smells": smells,

        }



        file_results.append(file_result)

        stats["files_analyzed"] += 1



    overall_score = score_project(file_results)



    total_loc = sum(fr["metrics"]["loc"] for fr in file_results)

    cc_values = [fr["metrics"]["cyclomatic_complexity"] for fr in file_results]

    avg_cc = round(sum(cc_values) / len(cc_values), 1) if cc_values else 0.0

    total_smells = sum(len(fr["smells"]) for fr in file_results)

    duration_ms = int((time.perf_counter() - t0) * 1000)



    return {

        "overall_score": overall_score,

        "files": file_results,

        "summary": {

            "files_analyzed": len(file_results),

            "total_loc": total_loc,

            "avg_cyclomatic_complexity": avg_cc,

            "total_smells": total_smells,

        },

        "scan_meta": {

            "scan_id": str(uuid.uuid4()),

            "completed_at": datetime.now(timezone.utc).isoformat(),

            "analysis_duration_ms": duration_ms,

            "llm_refine_enabled": llm_refine_enabled,

            "sensitivity": chosen_sensitivity,

            "analysis_stats": stats,

            "limits": {

                "max_analyze_file_bytes": config.MAX_ANALYZE_FILE_BYTES,

                "max_physical_lines": config.MAX_PHYSICAL_LINES,

                "max_files_to_analyze": config.MAX_FILES_TO_ANALYZE,

            },

        },

        "smell_catalog": get_smell_catalog(),

        "evaluation_metrics": get_evaluation_metrics(),

    }


