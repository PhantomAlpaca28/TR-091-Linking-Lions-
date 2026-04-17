import logging
import os
import shutil
import socket
import uuid
import zipfile
from urllib.error import HTTPError
from urllib.parse import urlparse
import urllib.request
import json

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.db import init_db, get_history, get_human_sync, set_smell_acceptance
from backend.analyzer import analyze_directory

logger = logging.getLogger(__name__)

app = FastAPI(title="Tech Debt Advisor API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

TEMP_DIR = os.path.join(os.path.dirname(__file__), "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# How long (seconds) to wait on any GitHub network call
GITHUB_TIMEOUT = 30


# Initialize DB on startup
@app.on_event("startup")
def startup_event():
    init_db()


class RepoRequest(BaseModel):
    url: str
    sensitivity: str = "balanced"


class HumanSyncAcceptRequest(BaseModel):
    scan_id: int
    smell_id: str
    accepted: bool


def normalize_github_url(url: str) -> tuple[str, str, str]:
    """
    Returns: (canonical_base_url, owner, repo)

    Accepts common GitHub URL shapes:
      - https://github.com/owner/repo
      - https://github.com/owner/repo/
      - https://github.com/owner/repo.git
      - https://github.com/owner/repo/tree/main
    """
    if not url:
        raise HTTPException(status_code=400, detail="GitHub URL is required")

    raw = url.strip()
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = "https://" + raw

    parsed = urlparse(raw)
    if not parsed.netloc or "github.com" not in parsed.netloc:
        raise HTTPException(status_code=400, detail="Must be a github.com repository URL")

    path_parts = [p for p in parsed.path.split("/") if p]
    if len(path_parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL format")

    owner = path_parts[0]
    repo = path_parts[1]
    if repo.endswith(".git"):
        repo = repo[:-4]

    canonical_base = f"https://github.com/{owner}/{repo}"
    return canonical_base, owner, repo


def get_default_branch(owner: str, repo: str) -> str:
    """
    Ask the GitHub API for the repo's actual default branch.
    Falls back to 'main' if the API call fails (e.g. rate-limited, no token).
    Bug fix #3: previously the code only tried 'main' then 'master', missing any
    other branch name and always failing for those repos.
    """
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    req = urllib.request.Request(api_url, headers={"Accept": "application/vnd.github+json"})
    try:
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(GITHUB_TIMEOUT)
        try:
            with urllib.request.urlopen(req) as resp:
                meta = json.loads(resp.read().decode())
                return meta.get("default_branch", "main")
        finally:
            socket.setdefaulttimeout(old_timeout)
    except Exception as exc:
        logger.warning("Could not fetch GitHub API metadata for %s/%s: %s — falling back to 'main'", owner, repo, exc)
        return "main"


def _urlretrieve_with_timeout(url: str, dest: str, timeout: int = GITHUB_TIMEOUT) -> None:
    """
    Wrapper around urlretrieve that enforces a socket timeout.
    Bug fix #2: the original code used urlretrieve with no timeout, which could
    block a server worker thread indefinitely on a slow or unresponsive connection.
    """
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        urllib.request.urlretrieve(url, dest)
    finally:
        socket.setdefaulttimeout(old_timeout)


@app.post("/analyze/github")
def analyze_github(request: RepoRequest):
    canonical_base, owner, repo = normalize_github_url(request.url)
    project_id = f"{owner}/{repo}"

    # Bug fix #3: resolve the real default branch instead of guessing main/master.
    default_branch = get_default_branch(owner, repo)
    zip_url = f"{canonical_base}/archive/refs/heads/{default_branch}.zip"
    logger.info("Downloading %s (branch: %s)", project_id, default_branch)

    target_dir = os.path.join(TEMP_DIR, str(uuid.uuid4()))
    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, "repo.zip")

    # Download the zip
    try:
        # Bug fix #2: timeout enforced via _urlretrieve_with_timeout
        _urlretrieve_with_timeout(zip_url, zip_path)
    except HTTPError as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        if e.code == 404:
            raise HTTPException(
                status_code=400,
                detail=f"Branch '{default_branch}' not found on GitHub. Check the repository URL."
            )
        raise HTTPException(status_code=400, detail=f"Failed to download repository: {e}")
    except Exception as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"Failed downloading repository: {e}")

    # Extract, analyse, clean up
    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(target_dir)

        # Remove the zip itself so it isn't analysed as source code
        os.remove(zip_path)

        result = analyze_directory(target_dir, project_id, request.sensitivity)

        # Bug fix #1: ignore_errors=True is sufficient — the bare `except: pass` block
        # was hiding real exceptions; removed entirely.
        shutil.rmtree(target_dir, ignore_errors=True)

        history = get_history(project_id)
        result["history"] = history
        return result
    except HTTPException:
        raise
    except Exception as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        logger.exception("analyze_github failed for %s", project_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/zip")
async def analyze_zip(file: UploadFile = File(...), sensitivity: str = Form("balanced")):
    # Bug fix #6: sanitise the filename to prevent path-traversal attacks.
    # os.path.basename strips any directory components from a crafted filename.
    safe_name = os.path.basename(file.filename or "upload.zip") or "upload.zip"
    project_id = safe_name.replace(".zip", "")

    target_dir = os.path.join(TEMP_DIR, str(uuid.uuid4()))
    os.makedirs(target_dir, exist_ok=True)
    zip_path = os.path.join(target_dir, safe_name)

    with open(zip_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    try:
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(target_dir)

        # Remove the zip itself so it isn't analysed as source code
        os.remove(zip_path)

        result = analyze_directory(target_dir, project_id, sensitivity)

        # Bug fix #1: same as above — bare except removed; ignore_errors=True is enough.
        shutil.rmtree(target_dir, ignore_errors=True)

        history = get_history(project_id)
        result["history"] = history
        return result
    except HTTPException:
        raise
    except Exception as e:
        shutil.rmtree(target_dir, ignore_errors=True)
        logger.exception("analyze_zip failed for %s", project_id)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history/{project_id}")
def get_project_history(project_id: str):
    return {"history": get_history(project_id)}


@app.get("/human-sync/{scan_id}")
def get_human_sync_endpoint(scan_id: int):
    return get_human_sync(scan_id)


@app.post("/human-sync/accept")
def accept_human_sync(req: HumanSyncAcceptRequest):
    return set_smell_acceptance(req.scan_id, req.smell_id, req.accepted)


# Mount the static directory to serve the Vanilla JS UI
app.mount("/", StaticFiles(directory="static", html=True), name="static")
