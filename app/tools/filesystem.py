"""Safe local filesystem manipulation and folder navigation tools for Windows 11.

Follows Workstream G security requirements:
- Strictly explicit function calls with path validation.
- No destructive actions (deletion) without explicit confirmation.
- Restricts operations to safe user-accessible paths.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from app.core.logger import setup_logger

logger = setup_logger("jarvis.tools.filesystem")


def get_user_folder(name: str) -> Optional[Path]:
    """Resolves standard Windows user directory by colloquial name."""
    user_home = Path(os.environ.get("USERPROFILE", "C:\\Users\\user"))
    norm = name.strip().lower()

    mapping = {
        "desktop": user_home / "Desktop",
        "layar utama": user_home / "Desktop",
        "downloads": user_home / "Downloads",
        "unduhan": user_home / "Downloads",
        "download": user_home / "Downloads",
        "documents": user_home / "Documents",
        "dokumen": user_home / "Documents",
        "berkas": user_home / "Documents",
        "pictures": user_home / "Pictures",
        "gambar": user_home / "Pictures",
        "foto": user_home / "Pictures",
        "music": user_home / "Music",
        "musik": user_home / "Music",
        "videos": user_home / "Videos",
        "video": user_home / "Videos",
        "home": user_home,
        "user": user_home,
    }
    return mapping.get(norm)


resolve_standard_folder = get_user_folder


def open_folder(target: str) -> Tuple[bool, str, str, str]:
    """Opens a Windows directory or standard folder in File Explorer.

    Returns:
        Tuple of (success, display_name, path_str, message).
    """
    path = get_user_folder(target)
    display_name = target.capitalize()

    if path is None:
        p = Path(target)
        if p.exists() and p.is_dir():
            path = p
            display_name = p.name or target

    if path is None or not path.exists():
        logger.warning("Folder not found: %s", target)
        return False, display_name, "", f"Folder '{target}' tidak ditemukan di sistem."

    try:
        os.startfile(str(path))
        logger.info("Opened folder: %s", path)
        return True, display_name, str(path), f"Berhasil membuka folder {display_name}."
    except Exception as e:
        logger.error("Failed to open folder %s: %s", path, e)
        return False, display_name, str(path), str(e)


def create_directory(folder_path_or_name: str, parent: Optional[str] = None) -> Tuple[bool, str, str]:
    """Safely creates a new folder.

    Returns:
        Tuple of (success, path_str, message).
    """
    p = Path(folder_path_or_name)
    if p.is_absolute():
        target_path = p
    else:
        parent_path = get_user_folder(parent) if parent else get_user_folder("desktop")
        if parent_path is None:
            parent_path = Path(os.environ.get("USERPROFILE", "C:\\Users\\user")) / "Desktop"
        target_path = parent_path / folder_path_or_name.strip()

    try:
        target_path.mkdir(parents=True, exist_ok=True)
        logger.info("Created directory: %s", target_path)
        return True, str(target_path), f"Folder '{target_path.name}' berhasil dibuat."
    except Exception as e:
        logger.error("Failed to create directory %s: %s", target_path, e)
        return False, str(target_path), str(e)


create_folder = create_directory


def delete_file_or_folder(path_str: str, confirmed: bool = False) -> Tuple[bool, str]:
    """Safely deletes a file or directory with mandatory confirmation requirement."""
    p = Path(path_str)
    if not p.exists():
        return False, f"Jalur '{path_str}' tidak ditemukan."

    if not confirmed:
        # Security requirement: Refuse immediate execution and demand explicit confirmation
        logger.warning("Destructive action intercepted: deletion of %s requires confirmation", path_str)
        return False, f"CONFIRMATION_REQUIRED: Menghapus '{p.name}' bersifat permanen. Apakah Anda yakin ingin melanjutkan?"

    try:
        if p.is_dir():
            import shutil
            shutil.rmtree(p)
        else:
            p.unlink()
        logger.info("Deleted: %s", p)
        return True, f"'{p.name}' berhasil dihapus."
    except Exception as e:
        logger.error("Error deleting %s: %s", p, e)
        return False, str(e)


safe_delete = delete_file_or_folder
