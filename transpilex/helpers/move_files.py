import shutil
from pathlib import Path


def move_files(source_folder: Path, destination_folder: Path, ignore_list: list[str] = None):
    """
    Moves all files from source_folder to destination_folder.
    Ignores files listed in ignore_list (if provided).

    :param source_folder: Path to the folder containing files to move.
    :param destination_folder: Destination folder path.
    :param ignore_list: Optional list of filenames to skip.
    """
    if ignore_list is None:
        ignore_list = []

    source_folder = Path(source_folder)
    destination_folder = Path(destination_folder)
    destination_folder.mkdir(parents=True, exist_ok=True)

    for file_path in source_folder.glob("*"):
        if file_path.is_file() and file_path.name not in ignore_list:
            destination = destination_folder / file_path.name
            shutil.move(str(file_path), str(destination))

    if not any(source_folder.iterdir()):
        source_folder.rmdir()
