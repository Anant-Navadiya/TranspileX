import shutil
from pathlib import Path

from transpilex.helpers.logs import Log


def copy_assets(source_path: Path, destination_path: Path, preserve=None, exclude=None):
    """
    Cleans destination_path (except items in preserve), then copies assets from source_path,
    skipping any items listed in exclude. Only runs if source_path exists.
    """
    source = Path(source_path)

    if not source.exists():
        Log.warning(f"Assets source not found at {source}")
        return

    destination = Path(destination_path)
    preserve = set(preserve or [])
    exclude = set(exclude or [])

    # Ensure destination exists
    destination.mkdir(parents=True, exist_ok=True)

    # Clean destination except preserved items
    Log.info(f"Cleaning {destination}{f' preserving: {preserve}' if preserve else ''}")
    for item in destination.iterdir():
        if item.name in preserve:
            Log.preserved(str(item))
            continue
        if item.is_dir():
            shutil.rmtree(item)
            Log.removed(str(item))
        else:
            item.unlink()
            Log.removed(str(item))

    # Copy new assets, skipping excluded names
    for item in source.iterdir():
        if item.name in exclude:
            Log.info(f"Skipping (excluded): {item.name}")
            continue

        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
        Log.copied(f"{item} → {target}")


def copy_assets_in_public(source_assets_path: Path, destination_path: Path,
                          candidates=None):
    if candidates is None:
        candidates = ["images", "img", "media", "data", "json"]

    destination_path.mkdir(parents=True, exist_ok=True)

    copied = set()

    for name in candidates:
        src = source_assets_path / name
        if src.exists() and src.is_dir():
            dest = destination_path / name
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(src, dest)
            copied.add(name)
            Log.copied(f"{src} → {dest}")

    return copied
