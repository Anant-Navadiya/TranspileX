import shutil
from pathlib import Path
from typing import Union, List, Set, Optional

from transpilex.helpers.messages import Messenger

def copy_items(
        source_paths: Union[str, Path, List[Union[str, Path]]],
        destination_path: Union[str, Path],
        clean_destination: bool = False,
        preserve: Optional[List[str]] = None,
):
    """
    Copies one or more files or directories to a destination path.

    This function is a generic utility for copying assets. It can handle a single
    source item (file or directory) or a list of them. It also provides an
    option to clean the destination directory before copying, while preserving
    specified items.

    Args:
        source_paths: A single path (str or Path) or a list of paths to be copied.
        destination_path: The path (str or Path) to the destination. If copying a
                          single file, this can be a new filename. Otherwise, it
                          must be a directory.
        clean_destination: If True, the destination directory will be cleared
                           before copying, except for items in `preserve`. This
                           option only applies when the destination is a directory.
        preserve: A list of filenames or directory names to keep in the
                  destination directory if `clean_destination` is True.
    """
    # Normalize paths
    destination = Path(destination_path)
    if not isinstance(source_paths, list):
        source_paths = [source_paths]
    sources = [Path(p) for p in source_paths]

    # Determine if destination is a directory and prepare it
    is_dest_dir = len(sources) > 1 or destination.is_dir()

    # If the destination is a directory, create it and handle cleaning.
    if is_dest_dir:
        destination.mkdir(parents=True, exist_ok=True)
        if clean_destination:
            preserve_set: Set[str] = set(preserve or [])
            Messenger.info(
                f"Cleaning '{destination}'"
                f"{f' while preserving: {preserve_set}' if preserve_set else ''}"
            )
            for item in destination.iterdir():
                if item.name in preserve_set:
                    Messenger.preserved(item.name)
                    continue
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                        Messenger.removed(item.name)
                    else:
                        item.unlink()
                        Messenger.removed(item.name)
                except OSError as e:
                    Messenger.error(f"Error removing {item}: {e}")

    for source in sources:
        if not source.exists():
            Messenger.warning(f"Source not found and was skipped: {source}")
            continue

        # If destination is a directory, the target is inside it.
        # Otherwise, the target is the destination path itself (for single-item copies).
        target = destination / source.name if is_dest_dir else destination

        # For single file copies, ensure the parent directory exists.
        if not is_dest_dir:
            target.parent.mkdir(parents=True, exist_ok=True)

        try:
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
                Messenger.copied(f"{source.name} -> {target}")
            elif source.is_file():
                shutil.copy2(source, target)
                Messenger.copied(f"{source.name} -> {target}")
        except Exception as e:
            Messenger.error(f"Failed to copy {source.name} to {target}: {e}")