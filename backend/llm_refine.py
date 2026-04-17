"""Optional OpenAI refinement for refactoring snippets (before/after)."""

import json
import os
import urllib.error
import urllib.request

try:
    from backend import config
except ModuleNotFoundError:
    import config

MAX_CODE_CHARS = 14_000


def _get_api_key():
    return os.getenv("OPENAI_API_KEY", "").strip()


def _get_model():
    return os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


def refine_smells_for_file(code: str, language: str, filename: str, smells: list) -> list:
    """
    If OPENAI_API_KEY is set, ask the model for improved `after` refactoring snippets.
    Falls back to input smells on any failure.
    """
    if not smells or not _get_api_key():
        return smells

    truncated = code if len(code) <= MAX_CODE_CHARS else code[:MAX_CODE_CHARS] + "\n/* … truncated … */\n"

    payload = {
        "model": _get_model(),
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": (
                    "You assist with code quality. Given source and a list of smell objects "
                    "(each has catalog_id, name, line_start, line_end, before, suggestion), "
                    "return JSON: {\"refinements\": [{\"index\": 0-based index, \"after\": string of refactored code "
                    "or explanation, \"before\": optional improved excerpt of problematic code}]}. "
                    "Keep `after` as concrete code when possible. Do not wrap in markdown fences inside JSON strings."
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "filename": filename,
                        "language": language,
                        "smells": [
                            {
                                "index": i,
                                "catalog_id": s.get("catalog_id"),
                                "name": s.get("name"),
                                "line_start": s.get("line_start"),
                                "line_end": s.get("line_end"),
                                "before": (s.get("before") or "")[:2000],
                                "suggestion": s.get("suggestion"),
                            }
                            for i, s in enumerate(smells)
                        ],
                        "code": truncated,
                    },
                    ensure_ascii=False,
                ),
            },
        ],
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_get_api_key()}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=config.OPENAI_TIMEOUT_SEC) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return smells

    try:
        text = body["choices"][0]["message"]["content"]
        data = json.loads(text)
    except (KeyError, IndexError, json.JSONDecodeError, TypeError):
        return smells

    refinements = data.get("refinements") or []
    out = [dict(s) for s in smells]
    for r in refinements:
        try:
            idx = int(r.get("index", -1))
        except (TypeError, ValueError):
            continue
        if idx < 0 or idx >= len(out):
            continue
        after = r.get("after")
        if isinstance(after, str) and after.strip():
            out[idx]["after"] = after.strip()
            out[idx]["llm_refined"] = True
        before = r.get("before")
        if isinstance(before, str) and before.strip():
            out[idx]["before"] = before.strip()

    return out
