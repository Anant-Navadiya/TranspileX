import shutil
from pathlib import Path

from transpilex.helpers.logs import Log


def apply_casing(name, case_type):
    if case_type == "snake":
        s1 = name.replace(" ", "-").replace("_", "-")
        s2 = ''.join(['-' + c.lower() if c.isupper() else c for c in s1]).lstrip('-')
        return s2.lower()
    elif case_type == "pascal":
        return ''.join(word.capitalize() for word in name.replace("-", " ").replace("_", " ").split())
    return name


def process_file_name(file_name):
    """
    Dummy processor — customize based on your pattern.
    Returns: prefix, folder_name, file_base_name, model_name
    Example: "user-profile.html" → ("", "user", "profile", "Profile")
    """
    base = Path(file_name).stem
    parts = base.split('-')
    if len(parts) >= 2:
        folder_name = apply_casing(parts[0], "snake")
        file_base_name = apply_casing(parts[-1], "snake")
        model_name = apply_casing(parts[-1], "pascal")
        return "", folder_name, file_base_name, model_name
    return "", base, base, base.capitalize()


def restructure_files(source_path: Path, destination_path: Path, new_extension=None,
                      ignore_list: list[str] | None = None,
                      casing="snake",
                      keep_underscore=False):
    """
    Restructures files from a source folder to a destination folder,
    applying casing conventions and changing file extensions.

    Args:
        source_path (Path): The source directory.
        destination_path (Path): The destination directory.
        new_extension (str, optional): The new file extension (e.g., ".html.erb"). Defaults to None.
        ignore_list (list, optional): A list of directory or file names to skip.
                                      Defaults to ['assets', 'gulpfile.js', ...].
        casing (str, optional): The casing convention for folder names ("snake" or "kebab"). Defaults to "snake".
        keep_underscore (bool, optional): If True, preserves underscores in file names
                                          instead of converting them to hyphens. Defaults to False.
    """
    copied_count = 0

    default_ignores = ["assets", "node_modules", ".git", "dist",
                       "gulpfile.js", "package.json", "plugins.config.js"]
    ignores = set(default_ignores + (ignore_list or []))

    destination_path.mkdir(parents=True, exist_ok=True)

    for file in source_path.rglob("*"):
        relative_parts = file.relative_to(source_path).parts
        if any(part in ignores for part in relative_parts):
            continue

        if not file.is_file():
            continue

        base_name = file.stem
        folder_name_parts = []
        final_file_name = "index"

        if '-' in base_name:
            name_parts = base_name.split('-')
            final_file_name = name_parts[-1]
            folder_name_parts = name_parts[:-1]
        elif '_' in base_name and not keep_underscore:
            name_parts = base_name.split('_')
            final_file_name = name_parts[-1]
            folder_name_parts = name_parts[:-1]
        else:
            final_file_name = base_name
            pass

        processed_folder_parts = [apply_casing(part, "kebab") for part in folder_name_parts]

        if keep_underscore:
            processed_file_name = final_file_name
        else:
            processed_file_name = apply_casing(final_file_name, casing)

        final_ext = new_extension if new_extension.startswith(".") else f".{new_extension}"
        target_dir = destination_path / Path(*processed_folder_parts)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{processed_file_name}{final_ext}"

        shutil.copy(file, target_file)
        Log.processed(f"{file.name} → {target_file.relative_to(destination_path)}")
        copied_count += 1

    Log.info(f"{copied_count} files processed and saved in {destination_path} with '{new_extension}' extension.")
