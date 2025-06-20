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


def restructure_files(src_folder, dist_folder, new_extension=None, skip_dirs=None, casing="snake"):
    src_path = Path(src_folder)
    dist_path = Path(dist_folder)
    copied_count = 0

    if skip_dirs is None:
        skip_dirs = []

    dist_path.mkdir(parents=True, exist_ok=True)

    for file in src_path.rglob("*"):
        if not file.is_file() or any(skip in file.parts for skip in skip_dirs):
            continue

        base_name = file.stem
        folder_name_parts = []
        final_file_name = "index"

        if '-' in base_name:
            name_parts = [part.replace("_", "-") for part in base_name.split('-')]
            final_file_name = name_parts[-1]
            folder_name_parts = name_parts[:-1]
        else:
            folder_name_parts = [base_name.replace("_", "-")]

        processed_folder_parts = [apply_casing(part, casing) for part in folder_name_parts]
        processed_file_name = apply_casing(final_file_name, casing)

        final_ext = new_extension if new_extension.startswith(".") else f".{new_extension}"
        target_dir = dist_path / Path(*processed_folder_parts)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{processed_file_name}{final_ext}"

        shutil.copy(file, target_file)
        print(f"📁 Copied: {file.name} → {target_file.relative_to(dist_path)}")
        copied_count += 1

    print(f"\n✅ {copied_count} files restructured.")
