from pathlib import Path


def folder_exists(folder_path: Path) -> bool:
    """Return True if the folder exists and is a directory."""
    return folder_path.is_dir()


def file_exists(file_path: Path) -> bool:
    """Return True if the file exists and is a file."""
    return file_path.is_file()