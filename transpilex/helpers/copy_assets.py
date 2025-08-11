import shutil
from pathlib import Path

from transpilex.helpers.messages import Messenger


def copy_assets(source_path: Path, destination_path: Path, preserve=None, exclude=None):
    """
    Cleans destination_path (except items in preserve), then copies assets from source_path,
    skipping any items listed in exclude. Only runs if source_path exists.
    """
    source = Path(source_path)

    if not source.exists():
        Messenger.warning(f"Assets source not found at {source}")
        return

    destination = Path(destination_path)
    preserve = set(preserve or [])
    exclude = set(exclude or [])

    # Ensure destination exists
    destination.mkdir(parents=True, exist_ok=True)

    # Clean destination except preserved items
    Messenger.info(f"Cleaning {destination}{f' preserving: {preserve}' if preserve else ''}")
    for item in destination.iterdir():
        if item.name in preserve:
            Messenger.preserved(str(item))
            continue
        if item.is_dir():
            shutil.rmtree(item)
            Messenger.removed(str(item))
        else:
            item.unlink()
            Messenger.removed(str(item))

    # Copy new assets, skipping excluded names
    for item in source.iterdir():
        if item.name in exclude:
            Messenger.info(f"Skipping (excluded): {item.name}")
            continue

        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
        Messenger.copied(f"{item} → {target}")
