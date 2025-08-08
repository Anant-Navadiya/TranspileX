import shutil
from pathlib import Path

from transpilex.helpers.messages import Messenger


def copy_assets(source_path: Path, destination_path: Path, preserve=None):
    """
    Cleans the destination_path (except for items listed in preserve),
    then copies assets from source_path to destination_path.
    Only runs if source_path exists.
    """
    source = Path(source_path)

    if not source.exists():
        Messenger.warning(f"Assets source not found at {source}")
        return

    destination = Path(destination_path)
    preserve = set(preserve or [])

    # Ensure destination exists
    destination.mkdir(parents=True, exist_ok=True)

    # Clean destination except preserved items
    Messenger.info(f"Cleaning '{destination}'{f' preserving: {preserve}' if preserve else ''}")

    for item in destination.iterdir():
        if item.name in preserve:
            Messenger.preserved(f"Preserved: {item}")
            continue
        if item.is_dir():
            shutil.rmtree(item)
            Messenger.removed(f"Removed folder: {item}")
        else:
            item.unlink()
            Messenger.removed(f"Removed file: {item}")

    # Copy new assets
    Messenger.info(f"Copying assets from '{source}' to '{destination}'")
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
        Messenger.success(f"Copied: {item} → {target}")
