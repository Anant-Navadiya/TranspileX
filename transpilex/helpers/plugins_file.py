from pathlib import Path

from transpilex.helpers.copy_items import copy_items
from transpilex.helpers.logs import Log


def plugins_file(source_folder: Path, destination_folder: Path):
    source_path = source_folder / "plugins.config.js"
    destination_path = destination_folder / "plugins.config.js"

    if source_path.exists():
        copy_items(source_path, destination_path)
        Log.info(f"plugins.config.js is ready at: {destination_path}")
        return True
    else:
        return False
