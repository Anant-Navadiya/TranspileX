import json
from pathlib import Path


def update_package_json(source_folder: str, destination_folder: str, project_name: str):
    """
    Ensures a valid package.json exists in source_folder.
    - If present, replaces its 'devDependencies'
    - If not present, creates a new one with the given project name
    """

    source_path = Path(source_folder) / "package.json"
    destination_path = Path(destination_folder) / "package.json"

    dev_deps = {
        "autoprefixer": "^10.4.0",
        "browser-sync": "^3.0.2",
        "cssnano": "^7.0.0",
        "gulp": "^4.0.2",
        "gulp-npm-dist": "^1.0.4",
        "gulp-plumber": "^1.2.1",
        "gulp-postcss": "^10.0.0",
        "gulp-rename": "^2.0.0",
        "gulp-sass": "^5.0.0",
        "node-sass-tilde-importer": "^1.0.2",
        "pixrem": "^5.0.0",
        "postcss": "^8.3.11",
        "sass": "^1.43.4"
    }

    # Load existing package.json or start fresh
    if source_path.exists():
        try:
            with open(source_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            print("⚠️ Invalid package.json, creating new one...")
            data = {}
    else:
        print(f"📦 package.json not found in {source_folder}, creating new one...")
        data = {}

    # Apply defaults
    data["name"] = data.get("name") or project_name.lower().replace(" ", "-")
    data["version"] = data.get("version") or "1.0.0"
    data["devDependencies"] = dev_deps

    # Write to destination folder
    with open(destination_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    print(f"✅ package.json ready at: {destination_path}")
