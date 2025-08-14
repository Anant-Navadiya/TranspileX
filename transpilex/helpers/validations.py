from pathlib import Path


def folder_exists(folder_path: Path) -> bool:
    """Return True if the folder exists and is a directory."""
    return folder_path.is_dir()
