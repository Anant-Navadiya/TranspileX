import json
from pathlib import Path
from typing import Dict, Any, Optional, Set
from transpilex.helpers.logs import Log


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
            Log.warning(f"Invalid JSON in {source_path}, creating a new package.json...")
            data = {}
    else:
        Log.warning(f"package.json not found in root, creating a new one...")
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

    Log.info(f"package.json is ready at: {destination_path}")


def sync_package_json(
        source_folder: Path,
        destination_folder: Path,
        *,
        ignore_gulp: bool = True,
        extra_ignore: Optional[Set[str]] = None,
):
    """
    Sync ONLY dependencies/devDependencies from source -> destination and write destination/package.json.

    Rules:
    - If a package exists in destination, keep destination's version (no upgrades).
    - If a package exists only in source, add it with the source version.
    - Gulp-related devDependencies are removed by default (ignore_gulp=True).
    - No other fields in destination package.json are modified.
    - If destination package.json doesn't exist but source does, create a new file with the merged deps/devDeps.
    - If neither exists, creates a minimal file with empty deps/devDeps.

    Returns the final destination package.json dict.
    """
    GULP_DEFAULT: Set[str] = {
        "@babel/core", "@babel/preset-env", "browser-sync", "clean-css", "cross-env", "del",
        "gulp", "gulp-babel", "gulp-if", "gulp-ignore", "gulp-npm-dist",
        "gulp-autoprefixer", "gulp-clean-css", "gulp-concat", "gulp-file-include",
        "gulp-newer", "gulp-rename", "gulp-rtlcss", "gulp-sass", "gulp-sourcemaps", "gulp-uglify",
    }

    source_path = source_folder / "package.json"
    destination_path = destination_folder / "package.json"

    # read (inline)
    try:
        src_pkg: Dict[str, Any] = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else {}
    except Exception:
        src_pkg = {}

    try:
        dst_pkg: Dict[str, Any] = json.loads(destination_path.read_text(encoding="utf-8")) if destination_path.exists() else {}
    except Exception:
        dst_pkg = {}

    src_deps = src_pkg.get("dependencies") or {}
    src_dev = src_pkg.get("devDependencies") or {}
    dst_deps = dst_pkg.get("dependencies") or {}
    dst_dev = dst_pkg.get("devDependencies") or {}

    # merge
    merged_deps: Dict[str, str] = dict(dst_deps)
    for name, ver in src_deps.items():
        merged_deps.setdefault(name, ver)

    merged_dev: Dict[str, str] = dict(dst_dev)
    for name, ver in src_dev.items():
        merged_dev.setdefault(name, ver)

    # remove gulp-like dev deps
    if ignore_gulp:
        ignore = set(GULP_DEFAULT) | (set(extra_ignore) if extra_ignore else set())

        def is_gulp_like(n: str) -> bool:
            return "gulp" in n or n in ignore

        merged_dev = {k: v for k, v in merged_dev.items() if not is_gulp_like(k)}

    # build output (preserve all other destination fields)
    out = dict(dst_pkg) if dst_pkg else {}
    out["dependencies"] = dict(sorted(merged_deps.items())) if merged_deps else out.get("dependencies", {})
    out["devDependencies"] = dict(sorted(merged_dev.items())) if merged_dev else out.get("devDependencies", {})

    # Ensure folder exists and write
    destination_folder.mkdir(parents=True, exist_ok=True)
    with open(destination_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")

    Log.info(f"package.json is ready at: {destination_path}")

    return out
