import shutil
from pathlib import Path

from transpilex.helpers.logs import Log



def empty_folder_contents(folder_path: Path, skip=None):
    """
    Deletes all contents inside the given folder (files and subfolders),
    but keeps the folder itself.

    :param folder_path: The folder to empty.
    :param skip: Optional list of file or directory names to skip from deletion.
    """
    folder_path = Path(folder_path)
    skip = set(skip or [])

    if not folder_path.exists() or not folder_path.is_dir():
        return

    for item in folder_path.iterdir():
        if item.name in skip:
            # Skip this item
            continue
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            Log.error(f"Error removing {item}: {e}")

    if not any(folder_path.iterdir()):
        folder_path.rmdir()
