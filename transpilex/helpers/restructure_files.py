import os
import shutil
from pathlib import Path


# ==== Shared Utilities ====

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


def restructure_files(src_folder, dist_folder, new_extension=None, skip_dirs=None, casing="snake", keep_underscore=False):
    """
    Restructures files from a source folder to a destination folder,
    applying casing conventions and changing file extensions.

    Args:
        src_folder (str or Path): The source directory.
        dist_folder (str or Path): The destination directory.
        new_extension (str, optional): The new file extension (e.g., ".html.erb"). Defaults to None.
        skip_dirs (list, optional): A list of directory names to skip. Defaults to None.
        casing (str, optional): The casing convention for folder names ("snake" or "kebab"). Defaults to "snake".
        keep_underscore (bool, optional): If True, preserves underscores in file names
                                                      instead of converting them to hyphens. Defaults to False.
    """
    src_path = Path(src_folder)
    dist_path = Path(dist_folder)
    copied_count = 0

    if skip_dirs is None:
        skip_dirs = []

    dist_path.mkdir(parents=True, exist_ok=True)

    for file in src_path.rglob("*"):
        if not file.is_file() or any(skip in file.parts for skip in skip_dirs):
            continue

        base_name = file.stem # e.g., "my-page" or "another_file"
        folder_name_parts = []
        final_file_name = "index" # Default if no hyphen is found for splitting

        # Determine folder parts and the actual file name part
        if '-' in base_name:
            name_parts = base_name.split('-')
            final_file_name = name_parts[-1]
            folder_name_parts = name_parts[:-1]
        elif '_' in base_name and not keep_underscore:
            # If underscores are to be converted and found in base_name
            name_parts = base_name.split('_')
            final_file_name = name_parts[-1]
            folder_name_parts = name_parts[:-1]
        else:
            # No hyphen, or underscores are to be kept in filename
            final_file_name = base_name
            # If base_name itself is a folder name (e.g., 'about' -> 'about/index.html')
            # This logic might need refinement based on exact source structure rules.
            # For now, if it's a single part, it becomes the folder part, and file is 'index'.
            # If `base_name` is just a file like `home.html`, `final_file_name` will be `home`.
            # If `base_name` is `about-us.html`, `folder_name_parts` will be `['about']`, `final_file_name` will be `us`.
            # If `base_name` is `about_us.html` and `keep_underscore=True`, `final_file_name` will be `about_us`.
            # If `base_name` is `about_us.html` and `keep_underscore=False`, it will be split.
            pass # The initial assignment of final_file_name and folder_name_parts is sufficient here.


        # Apply casing to folder names
        # Ensure folder names are consistently kebab-case for Rails views
        processed_folder_parts = [apply_casing(part, "kebab") for part in folder_name_parts]

        # Apply casing to file name based on the new parameter
        if keep_underscore:
            processed_file_name = final_file_name # Keep as is
        else:
            processed_file_name = apply_casing(final_file_name, casing) # Apply casing (e.g., kebab)

        final_ext = new_extension if new_extension.startswith(".") else f".{new_extension}"
        target_dir = dist_path / Path(*processed_folder_parts)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{processed_file_name}{final_ext}"

        shutil.copy(file, target_file)
        print(f"📁 Copied: {file.name} → {target_file.relative_to(dist_path)}")
        copied_count += 1

    print(f"\n✅ {copied_count} files restructured.")
