from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

import zipfile
import os
import shutil
import subprocess
import uuid

from backend.analyzer import analyze_directory
from backend.db import init_db

app = FastAPI()

# Enable frontend connection
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "temp_upload"

init_db()


def clean_folder(path):
    if os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path)


# ZIP Upload Scan
@app.post("/scan-zip")
async def scan_zip(file: UploadFile = File(...)):

    clean_folder(UPLOAD_DIR)

    zip_path = os.path.join(
        UPLOAD_DIR,
        file.filename
    )

    with open(zip_path, "wb") as f:
        f.write(await file.read())

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        zip_ref.extractall(UPLOAD_DIR)

    result = analyze_directory(UPLOAD_DIR)

    return result


# GitHub Repo Scan
@app.post("/scan-repo")
async def scan_repo(repo_url: str = Form(...)):

    clean_folder(UPLOAD_DIR)

    repo_folder = os.path.join(
        UPLOAD_DIR,
        str(uuid.uuid4())
    )

    subprocess.run(
        ["git", "clone", repo_url, repo_folder],
        check=True
    )

    result = analyze_directory(repo_folder)

    return result