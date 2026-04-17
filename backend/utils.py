import os
from pathlib import PurePosixPath

LANGUAGE_EXTENSIONS = {
    ".py": "python",
    ".pyw": "python",
    ".java": "java",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".vue": "vue",
    ".svelte": "svelte",
    ".go": "go",
    ".rs": "rust",
    ".c": "c",
    ".h": "c",
    ".cc": "cpp",
    ".cpp": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".cs": "csharp",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".scala": "scala",
    ".dart": "dart",
}


def detect_language(filename):

    _, ext = os.path.splitext(filename)

    return LANGUAGE_EXTENSIONS.get(ext.lower())


def read_file_safe(path):

    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    except OSError:
        try:
            with open(path, "r", encoding="latin-1") as f:
                return f.read()
        except OSError:
            return ""


def is_probably_binary(text_sample: str) -> bool:
    if not text_sample:
        return False
    if "\0" in text_sample:
        return True
    printable = sum(1 for c in text_sample if c in "\n\r\t" or 32 <= ord(c) < 127)
    return printable / max(len(text_sample), 1) < 0.85


def safe_upload_basename(filename: str | None) -> str:
    """Reject path traversal in upload names; require .zip."""
    if not filename:
        raise ValueError("Missing filename")
    base = os.path.basename(filename.replace("\\", "/"))
    if not base or base in (".", ".."):
        raise ValueError("Invalid filename")
    if not base.lower().endswith(".zip"):
        raise ValueError("Not a zip file")
    parts = PurePosixPath(base).parts
    if ".." in parts or any(p == "" for p in parts):
        raise ValueError("Invalid filename")
    return base

