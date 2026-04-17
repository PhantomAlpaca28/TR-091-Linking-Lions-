"""Bounded, path-safe ZIP extraction (no ZipFile.extractall for symlink / traversal edge cases)."""

from __future__ import annotations

import shutil
import zipfile
from pathlib import Path, PurePosixPath

from fastapi import HTTPException


def _reject_zip_member_name(name: str) -> bool:
    if not name or name.startswith("/") or name.startswith("\\"):
        return True
    # Windows absolute paths disguised as names
    if len(name) >= 2 and name[1] == ":":
        return True
    parts = PurePosixPath(name).parts
    return ".." in parts or any(p in ("", ".") for p in parts if p not in (".",))


def extract_zip_bounded(
    zip_path: str,
    destination: str,
    *,
    max_uncompressed_total: int,
    max_members: int,
    max_single_entry: int,
) -> None:
    """
    Extract regular files only, with aggregate size / count limits checked up front.
    Skips directory entries and oversize single members (others still extract).
    """
    dest_root = Path(destination).resolve()

    with zipfile.ZipFile(zip_path, "r") as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]

        if len(infos) > max_members:
            raise HTTPException(
                status_code=400,
                detail=f"Archive has too many entries (max {max_members}).",
            )

        total = 0
        for info in infos:
            total += int(info.file_size or 0)
        if total > max_uncompressed_total:
            raise HTTPException(
                status_code=400,
                detail="Archive expands to more data than allowed. Try a smaller project or raise TDS_MAX_ZIP_UNCOMPRESSED_MB.",
            )

        for info in infos:
            if _reject_zip_member_name(info.filename):
                raise HTTPException(status_code=400, detail="Archive contains unsafe path entries.")

            if int(info.file_size or 0) > max_single_entry:
                continue

            target = (dest_root / info.filename).resolve()
            try:
                target.relative_to(dest_root)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail="Invalid zip archive structure.") from exc

            target.parent.mkdir(parents=True, exist_ok=True)

            try:
                with zf.open(info, "r") as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, length=1024 * 256)
            except OSError as exc:
                raise HTTPException(status_code=400, detail=f"Failed to extract archive: {exc}") from exc
