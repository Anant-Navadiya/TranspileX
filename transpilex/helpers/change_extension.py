import os
import shutil
from pathlib import Path
import fnmatch

from transpilex.helpers.messages import Messenger


def change_extension_and_copy(
        new_extension: str,
        source_path: Path,
        destination_path: Path,
        ignore_list: list[str] | None = None
):
    """
    Recursively convert file extensions and copy to a dist folder, preserving structure.

    :param new_extension: New extension (e.g., 'php' or '.php')
    :param source_path: Source directory path
    :param destination_path: Output directory path
    :param ignore_list: List of directory names, file names, or glob patterns to skip.
                        Defaults include: assets, node_modules, .git, dist, build,
                        gulpfile.js, package.json, package-lock.json, pnpm-lock.yaml,
                        yarn.lock
    """

    if not source_path.exists() or not source_path.is_dir():
        Messenger.error(f"Source folder '{source_path}' does not exist or is not a directory.")
        return

    if not new_extension.startswith('.'):
        new_extension = '.' + new_extension

    default_ignores = [
        "assets", "node_modules", ".git", "dist",
        "gulpfile.js", "package.json", "plugins.config.js"
    ]
    ignores = set(default_ignores + (ignore_list or []))

    count = 0

    for root, dirs, files in os.walk(source_path):
        dirs[:] = [d for d in dirs if d not in ignores]

        root_path = Path(root)
        for fname in files:
            rel_path = (root_path / fname).relative_to(source_path)
            rel_str = rel_path.as_posix()

            if fname in ignores or any(fnmatch.fnmatch(rel_str, pat) for pat in ignores):
                continue

            if not Path(fname).suffix:
                continue

            new_name = Path(fname).stem.replace("_", "-") + new_extension
            destination = destination_path / rel_path.parent / new_name

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(root_path / fname, destination)

            Messenger.processed(f"{root_path / fname} → {destination}")
            count += 1

    Messenger.info(f"{count} files processed and saved in {destination_path} with '{new_extension}' extension.")


def change_extension(new_extension, src_path: Path, dist_path: Path):
    if not src_path.exists() or not src_path.is_dir():
        Messenger.error(f"Source path '{src_path}' does not exist or is not a directory.")
        return

    if not new_extension.startswith('.'):
        new_extension = '.' + new_extension

    count = 0
    for file in src_path.rglob("*"):
        if file.is_file() and file.suffix:
            relative_path = file.relative_to(src_path)

            # Replace underscores with dashes in the filename (not path)
            new_name = relative_path.stem.replace("_", "-") + new_extension
            destination = dist_path / relative_path.parent / new_name

            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(file, destination)

            Messenger.success(f"{file} → {destination}")
            count += 1

    Messenger.info(f"{count} files processed and saved in '{dist_path}' with '{new_extension}' extension.")
