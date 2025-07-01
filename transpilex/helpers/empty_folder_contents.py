import shutil
from pathlib import Path

from transpilex.helpers.messages import Messenger


def empty_folder_contents(folder_path: Path):
    """
    Deletes all contents inside the given folder (files and subfolders),
    but keeps the folder itself.

    :param folder_path: The folder to empty.
    """
    folder_path = Path(folder_path)

    if not folder_path.exists() or not folder_path.is_dir():
        return

    for item in folder_path.iterdir():
        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            Messenger.error(f"Error removing {item}: {e}")
