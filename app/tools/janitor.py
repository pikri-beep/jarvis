"""Workspace Janitor tool for cleaning and organizing Windows Desktop and Downloads.

Safely organizes loose files into categorized subfolders (Documents, Images, Installers,
Archives, Media, Code) without destructive operations or overwriting.
"""

import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.core.logger import setup_logger
from app.tools.filesystem import get_user_folder

logger = setup_logger("jarvis.tools.janitor")

# File extension categorization map
CATEGORY_EXTENSIONS: Dict[str, List[str]] = {
    "Documents": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".rtf", ".odt", ".md"],
    "Images": [".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico", ".tiff", ".psd"],
    "Installers": [".exe", ".msi", ".iso", ".dmg", ".pkg"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"],
    "Media": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg"],
    "Code": [".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json", ".sql", ".java", ".cpp", ".c", ".cs", ".go", ".rs", ".php", ".sh", ".bat", ".ps1"],
}

# Invert for fast lookup: extension -> category name
EXT_TO_CATEGORY: Dict[str, str] = {}
for category, exts in CATEGORY_EXTENSIONS.items():
    for ext in exts:
        EXT_TO_CATEGORY[ext.lower()] = category

# Files to always ignore
IGNORED_EXTENSIONS = {".lnk", ".ini", ".tmp", ".crdownload", ".part", ".downloading"}


def resolve_target_folder(target: str = "downloads") -> Optional[Path]:
    """Resolves target folder name ('downloads', 'desktop', or absolute path)."""
    norm = target.strip().lower()
    folder = get_user_folder(norm)
    if folder and folder.exists():
        return folder

    p = Path(target)
    if p.exists() and p.is_dir():
        return p

    return None


def get_file_category(file_path: Path) -> str:
    """Returns category name for a given file path based on suffix."""
    ext = file_path.suffix.lower()
    return EXT_TO_CATEGORY.get(ext, "Others")


def count_clutter(target: str = "downloads") -> int:
    """Counts the number of loose, unorganized files in the root of target folder."""
    folder = resolve_target_folder(target)
    if not folder or not folder.exists():
        return 0

    count = 0
    try:
        for entry in folder.iterdir():
            if entry.is_file() and not entry.name.startswith("."):
                if entry.suffix.lower() not in IGNORED_EXTENSIONS:
                    count += 1
    except Exception as e:
        logger.warning("Error counting clutter in %s: %s", target, e)
    return count


def scan_workspace(target: str = "downloads") -> Dict[str, Any]:
    """Scans root of target folder and categorizes loose files.

    Returns:
        Dict containing categories, file lists, and summary statistics.
    """
    folder = resolve_target_folder(target)
    if not folder:
        return {
            "success": False,
            "folder": target,
            "error": f"Folder '{target}' tidak ditemukan.",
            "total_files": 0,
            "categories": {},
        }

    categories: Dict[str, List[Dict[str, Any]]] = {
        cat: [] for cat in list(CATEGORY_EXTENSIONS.keys()) + ["Others"]
    }
    total_files = 0
    total_bytes = 0

    try:
        for item in folder.iterdir():
            if item.is_file() and not item.name.startswith("."):
                ext = item.suffix.lower()
                if ext in IGNORED_EXTENSIONS:
                    continue

                cat = get_file_category(item)
                size_bytes = item.stat().st_size
                categories[cat].append({
                    "name": item.name,
                    "path": str(item),
                    "size_bytes": size_bytes,
                    "size_mb": round(size_bytes / (1024 * 1024), 2),
                    "ext": ext,
                })
                total_files += 1
                total_bytes += size_bytes

        # Filter out empty categories
        non_empty_categories = {k: v for k, v in categories.items() if len(v) > 0}

        return {
            "success": True,
            "folder": str(folder),
            "folder_name": folder.name,
            "total_files": total_files,
            "total_mb": round(total_bytes / (1024 * 1024), 2),
            "categories": non_empty_categories,
        }
    except Exception as e:
        logger.error("Failed to scan folder %s: %s", folder, e)
        return {
            "success": False,
            "folder": str(folder),
            "error": str(e),
            "total_files": 0,
            "categories": {},
        }


def _get_unique_dest_path(dest_folder: Path, filename: str) -> Path:
    """Generates a non-conflicting destination path by appending (1), (2), etc."""
    target = dest_folder / filename
    if not target.exists():
        return target

    base = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while target.exists():
        target = dest_folder / f"{base} ({counter}){suffix}"
        counter += 1
    return target


def clean_workspace(target: str = "downloads", dry_run: bool = False) -> Dict[str, Any]:
    """Moves loose root files in target folder into categorized subfolders.

    Returns:
        Dict with moved count, moved items summary, and status message.
    """
    scan = scan_workspace(target)
    if not scan.get("success"):
        return scan

    folder = Path(scan["folder"])
    categories = scan.get("categories", {})
    moved_count = 0
    moved_details: List[Dict[str, str]] = []

    for category, file_list in categories.items():
        if category == "Others" and len(file_list) == 0:
            continue

        cat_folder = folder / category
        if not dry_run:
            cat_folder.mkdir(exist_ok=True)

        for file_info in file_list:
            src_path = Path(file_info["path"])
            if not src_path.exists():
                continue

            dest_path = _get_unique_dest_path(cat_folder, src_path.name)
            try:
                if not dry_run:
                    shutil.move(str(src_path), str(dest_path))
                moved_count += 1
                moved_details.append({
                    "name": src_path.name,
                    "from": str(src_path),
                    "to": str(dest_path),
                    "category": category,
                })
            except Exception as e:
                logger.warning("Failed to move file %s to %s: %s", src_path, dest_path, e)

    msg = f"Berhasil merapikan {moved_count} file di folder {folder.name}." if not dry_run else f"[Simulasi] {moved_count} file siap dirapikan."
    return {
        "success": True,
        "folder": str(folder),
        "moved_count": moved_count,
        "dry_run": dry_run,
        "details": moved_details,
        "message": msg,
    }
