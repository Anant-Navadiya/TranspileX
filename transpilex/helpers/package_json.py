import json
import requests
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


_VERSION_CACHE: Dict[str, str] = {}


def _get_latest_version(package_name: str) -> Optional[str]:
    """Fetches the latest package version from the npm registry."""
    if package_name in _VERSION_CACHE:
        return _VERSION_CACHE[package_name]

    try:
        url = f"https://registry.npmjs.org/{package_name}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        latest_version = data.get("dist-tags", {}).get("latest")
        if not latest_version:
            Log.warning(f"Could not find 'latest' version tag for package '{package_name}'.")
            return None

        _VERSION_CACHE[package_name] = latest_version
        return latest_version

    except requests.exceptions.RequestException as e:
        Log.error(f"Network error fetching version for '{package_name}': {e}")
        return None
    except (KeyError, json.JSONDecodeError):
        Log.warning(f"Received unexpected data structure for package '{package_name}'.")
        return None


def sync_package_json(
        source_folder: Path,
        destination_folder: Path,
        *,
        ignore_gulp: bool = True,
        extra_ignore: Optional[Set[str]] = None,
        extra_plugins: Optional[Dict[str, Optional[str]]] = None,
        extra_fields: Optional[Dict[str, Any]] = None,
):
    """
    Builds a package.json by using source as a base and merging dependencies
    and extra fields. Destination dependency versions have priority.
    """
    GULP_DEFAULT: Set[str] = {
        "@babel/core", "@babel/preset-env", "browser-sync", "clean-css", "cross-env", "del",
        "gulp", "gulp-babel", "gulp-if", "gulp-ignore", "gulp-npm-dist",
        "gulp-autoprefixer", "gulp-clean-css", "gulp-concat", "gulp-file-include",
        "gulp-newer", "gulp-rename", "gulp-rtlcss", "gulp-sass", "gulp-sourcemaps", "gulp-uglify",
    }

    source_path = source_folder / "package.json"
    destination_path = destination_folder / "package.json"

    try:
        src_pkg: Dict[str, Any] = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else {}
    except Exception:
        src_pkg = {}
    try:
        dst_pkg: Dict[str, Any] = json.loads(
            destination_path.read_text(encoding="utf-8")) if destination_path.exists() else {}
    except Exception:
        dst_pkg = {}

    # start with the source package as the base to preserve all its fields.
    out = dict(src_pkg)

    # get dependencies from both sources.
    src_deps, src_dev = src_pkg.get("dependencies", {}), src_pkg.get("devDependencies", {})
    dst_deps, dst_dev = dst_pkg.get("dependencies", {}), dst_pkg.get("devDependencies", {})

    # merge dependencies, giving priority to destination versions.
    merged_deps = {**src_deps, **dst_deps}
    merged_dev = {**src_dev, **dst_dev}

    # add extra plugins to main dependencies.
    if extra_plugins:
        processed_plugins: Dict[str, str] = {}
        for name, version in extra_plugins.items():
            if version:
                processed_plugins[name] = version
            else:
                latest_version = _get_latest_version(name)
                if latest_version:
                    processed_plugins[name] = f"^{latest_version}"
        merged_deps.update(processed_plugins)

    # filter gulp packages from devDependencies.
    if ignore_gulp:
        ignore = GULP_DEFAULT | (extra_ignore or set())
        merged_dev = {k: v for k, v in merged_dev.items() if not ("gulp" in k or k in ignore)}

    # update the output object with the final, sorted dependency lists.
    out["dependencies"] = dict(sorted(merged_deps.items())) if merged_deps else {}
    out["devDependencies"] = dict(sorted(merged_dev.items())) if merged_dev else {}

    # merge extra_fields with the highest priority.
    if extra_fields:
        for key, value in extra_fields.items():
            if key in out and isinstance(out.get(key), dict) and isinstance(value, dict):
                out[key] = {**out[key], **value}
            else:
                out[key] = value

    destination_folder.mkdir(parents=True, exist_ok=True)
    with open(destination_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")

    Log.info(f"package.json is ready at: {destination_path}")

    return out
