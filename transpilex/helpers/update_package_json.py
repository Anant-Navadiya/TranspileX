import json
from pathlib import Path
from transpilex.helpers.messages import Messenger


def update_package_json(source_folder: Path, destination_folder: Path, project_name: str):
    """
    Ensures a valid package.json exists and has the required devDependencies.
    - If a package.json exists in the source, its devDependencies are updated.
    - If not present in the source, a new one is created in the destination.

    Parameters:
    - source_folder: Path object for the source directory.
    - destination_folder: Path object for the destination directory.
    - project_name: The name to use for the project in package.json.
    """

    source_path = source_folder / "package.json"
    destination_path = destination_folder / "package.json"

    dev_deps = {
        "gulp": "^4.0.2",
        "gulp-autoprefixer": "^8.0.0",
        "gulp-clean-css": "^4.2.0",
        "gulp-concat": "^2.6.1",
        "gulp-rename": "^2.0.0",
        "gulp-rtlcss": "^2.0.0",
        "gulp-sass": "^5.1.0",
        "gulp-sourcemaps": "^3.0.0",
        "sass": "1.77.6"
    }

    # Load existing package.json or start fresh
    if source_path.exists():
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            Messenger.warning(f"Invalid JSON in {source_path}, creating a new package.json...")
            data = {}
    else:
        Messenger.warning(f"Package.json not found in {source_folder}, creating a new one...")
        data = {}

    # Apply defaults
    data["name"] = data.get("name") or project_name.lower().replace(" ", "-")
    data["version"] = data.get("version") or "1.0.0"

    # Merge new devDependencies with existing ones, instead of replacing them.
    if "devDependencies" in data and isinstance(data.get("devDependencies"), dict):
        # If devDependencies exist and is a dictionary, update it.
        # This adds new dependencies and updates versions for existing ones.
        data["devDependencies"].update(dev_deps)
    else:
        # Otherwise, just set devDependencies to our default list.
        data["devDependencies"] = dev_deps

    # Write to the destination folder
    with open(destination_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    Messenger.success(f"Package.json is ready at: {destination_path}")
