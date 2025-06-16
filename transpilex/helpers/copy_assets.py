import shutil
from pathlib import Path

def copy_assets(source_path, destination_path, preserve=None):
    """
    Cleans the destination_path (except for items listed in preserve),
    then copies assets from source_path to destination_path.

    Args:
        source_path (str | Path): Folder containing custom assets.
        destination_path (str | Path): CakePHP webroot or equivalent.
        preserve (list[str]): File/folder names to keep in destination.
    """
    source = Path(source_path)
    destination = Path(destination_path)
    preserve = set(preserve or [])

    # Ensure destination exists
    destination.mkdir(parents=True, exist_ok=True)

    # Step 1: Clean destination except preserved items
    print(f"\n🧹 Cleaning '{destination}' (preserving: {preserve})")
    for item in destination.iterdir():
        if item.name in preserve:
            print(f"⏭️ Preserved: {item}")
            continue
        if item.is_dir():
            shutil.rmtree(item)
            print(f"🗑️ Removed folder: {item}")
        else:
            item.unlink()
            print(f"🗑️ Removed file: {item}")

    # Step 2: Copy new assets
    print(f"\n📦 Copying assets from '{source}' to '{destination}'")
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target)
        else:
            shutil.copy2(item, target)
        print(f"✅ Copied: {item} → {target}")

    print("\n🎉 Asset copy completed.\n")
