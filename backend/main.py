from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

import logging
import os
import shutil
import stat
import subprocess
import time
import uuid
import zipfile

try:
    from backend import config
    from backend.analyzer import analyze_directory
    from backend.catalog import get_evaluation_metrics, get_smell_catalog
    from backend.utils import safe_upload_basename
    from backend.zip_extract import extract_zip_bounded
except ModuleNotFoundError:
    import config
    from analyzer import analyze_directory
    from catalog import get_evaluation_metrics, get_smell_catalog
    from utils import safe_upload_basename
    from zip_extract import extract_zip_bounded

log = logging.getLogger(__name__)

app = FastAPI(title=config.API_TITLE, version=config.API_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = config.UPLOAD_DIR


def normalize_sensitivity(value: str | None) -> str:
    chosen = (value or config.DEFAULT_SENSITIVITY).strip().lower()
    if chosen not in config.ALLOWED_SENSITIVITY:
        options = ", ".join(config.ALLOWED_SENSITIVITY)
        raise HTTPException(status_code=400, detail=f"Invalid sensitivity. Use one of: {options}.")
    return chosen


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/version")
def version():
    return {
        "version": config.API_VERSION,
        "title": config.API_TITLE,
        "default_sensitivity": config.DEFAULT_SENSITIVITY,
        "allowed_sensitivity": list(config.ALLOWED_SENSITIVITY),
    }


@app.get("/smell-catalog")
def smell_catalog():
    return get_smell_catalog()


@app.get("/evaluation-metrics")
def evaluation_metrics():
    return get_evaluation_metrics()


def clean_folder():
    if os.path.exists(UPLOAD_DIR):
        def handle_remove_readonly(func, path, _):
            os.chmod(path, stat.S_IWRITE)
            func(path)

        for _ in range(3):
            try:
                shutil.rmtree(UPLOAD_DIR, onexc=handle_remove_readonly)
                break
            except PermissionError:
                time.sleep(0.2)

    os.makedirs(UPLOAD_DIR)


def assert_safe_git_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        raise HTTPException(status_code=400, detail="Enter a valid git repository URL.")
    if len(u) > 2048:
        raise HTTPException(status_code=400, detail="Repository URL is too long.")
    for bad in ("\n", "\r", "\0"):
        if bad in u:
            raise HTTPException(status_code=400, detail="Invalid repository URL.")
    lower = u.lower()
    if "file://" in lower or lower.startswith("ext::"):
        raise HTTPException(status_code=400, detail="Unsupported or unsafe repository URL.")
    if not (lower.startswith("https://") or lower.startswith("http://") or u.startswith("git@")):
        raise HTTPException(status_code=400, detail="Enter a valid git repository URL.")
    return u


@app.post("/scan-zip")
async def scan_zip(file: UploadFile = File(...), sensitivity: str = Form(config.DEFAULT_SENSITIVITY)):
    clean_folder()
    chosen_sensitivity = normalize_sensitivity(sensitivity)

    try:
        safe_name = safe_upload_basename(file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    zip_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}_{safe_name}")

    payload = await file.read()
    if len(payload) > config.MAX_ZIP_UPLOAD_BYTES:
        mb = config.MAX_ZIP_UPLOAD_BYTES // (1024 * 1024)
        raise HTTPException(status_code=400, detail=f"Zip file is too large (max {mb}MB).")

    with open(zip_path, "wb") as f:
        f.write(payload)

    try:
        extract_zip_bounded(
            zip_path,
            UPLOAD_DIR,
            max_uncompressed_total=config.MAX_ZIP_UNCOMPRESSED_BYTES,
            max_members=config.MAX_ZIP_MEMBERS,
            max_single_entry=config.MAX_ZIP_SINGLE_ENTRY_BYTES,
        )
    except zipfile.BadZipFile as exc:
        if os.path.isfile(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass
        raise HTTPException(status_code=400, detail="Uploaded file is not a valid zip archive.") from exc
    except HTTPException:
        if os.path.isfile(zip_path):
            try:
                os.remove(zip_path)
            except OSError:
                pass
        raise

    log.info("scan-zip extracted to %s with sensitivity=%s", UPLOAD_DIR, chosen_sensitivity)
    return analyze_directory(UPLOAD_DIR, sensitivity=chosen_sensitivity)


@app.post("/scan-repo")
async def scan_repo(
    repo_url: str = Form(...),
    sensitivity: str = Form(config.DEFAULT_SENSITIVITY),
):
    clean_folder()
    repo_url = assert_safe_git_url(repo_url)
    chosen_sensitivity = normalize_sensitivity(sensitivity)
    repo_folder = os.path.join(UPLOAD_DIR, str(uuid.uuid4()))

    try:
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, repo_folder],
            capture_output=True,
            text=True,
            check=False,
            timeout=config.GIT_CLONE_TIMEOUT_SEC,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Git clone timed out after {config.GIT_CLONE_TIMEOUT_SEC}s.",
        ) from exc

    if clone.returncode != 0:
        err = (clone.stderr or clone.stdout or "").strip()
        raise HTTPException(status_code=400, detail=f"Failed to clone repository: {err}")

    log.info("scan-repo cloned to %s with sensitivity=%s", repo_folder, chosen_sensitivity)
    return analyze_directory(repo_folder, sensitivity=chosen_sensitivity)

