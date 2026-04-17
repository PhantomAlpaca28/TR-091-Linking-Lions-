"""
Central configuration. Override via environment variables for deployment.
Keeps API, analyzer, and ingest limits in one place.
"""

import os

# --- API / storage ---
API_TITLE = "Technical Debt Scorer"
API_VERSION = "1.1.0"
UPLOAD_DIR = os.getenv("TDS_UPLOAD_DIR", "temp_upload").strip() or "temp_upload"

# Debt sensitivity affects detection thresholds and score penalties.
ALLOWED_SENSITIVITY = ("strict", "balanced", "lenient")
DEFAULT_SENSITIVITY = os.getenv("TDS_DEFAULT_SENSITIVITY", "balanced").strip().lower()
if DEFAULT_SENSITIVITY not in ALLOWED_SENSITIVITY:
    DEFAULT_SENSITIVITY = "balanced"

# Uploaded .zip on disk (request body)
MAX_ZIP_UPLOAD_BYTES = int(os.getenv("TDS_MAX_ZIP_UPLOAD_MB", "25")) * 1024 * 1024

# Zip bomb guards: aggregate uncompressed size and entry count
MAX_ZIP_UNCOMPRESSED_BYTES = int(os.getenv("TDS_MAX_ZIP_UNCOMPRESSED_MB", "200")) * 1024 * 1024
MAX_ZIP_MEMBERS = int(os.getenv("TDS_MAX_ZIP_MEMBERS", "20000"))
MAX_ZIP_SINGLE_ENTRY_BYTES = int(os.getenv("TDS_MAX_ZIP_SINGLE_ENTRY_MB", "80")) * 1024 * 1024

# Per-file analysis (read + heuristic + optional LLM)
MAX_ANALYZE_FILE_BYTES = int(os.getenv("TDS_MAX_ANALYZE_FILE_KB", "600")) * 1024
MAX_PHYSICAL_LINES = int(os.getenv("TDS_MAX_PHYSICAL_LINES", "12000"))

# Stop after N analyzable files (fairness + DoS). Remaining matching files are skipped.
MAX_FILES_TO_ANALYZE = int(os.getenv("TDS_MAX_FILES_TO_ANALYZE", "500"))

# Git
GIT_CLONE_TIMEOUT_SEC = int(os.getenv("TDS_GIT_CLONE_TIMEOUT", "120"))

# OpenAI refinement
OPENAI_TIMEOUT_SEC = int(os.getenv("OPENAI_TIMEOUT_SEC", "75"))

# Directories skipped under any path component (lowercased match)
DEFAULT_SKIP_DIR_NAMES = frozenset(
    s.strip().lower()
    for s in os.getenv(
        "TDS_SKIP_DIRS",
        ".git,node_modules,.venv,venv,__pycache__,dist,build,.next,coverage,vendor,target,"
        ".turbo,.cache,.nuxt,.output,out,Pods,.gradle,.idea,.vscode,__MACOSX",
    ).split(",")
    if s.strip()
)
