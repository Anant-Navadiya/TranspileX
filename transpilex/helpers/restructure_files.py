import os
import shutil
from pathlib import Path

def restructure_files(src_folder, dist_folder, new_extension=None, skip_dirs=None, casing="snake"):
    """
    Restructure files from src_folder to dist_folder with:
    - Optional extension filtering
    - Infinite level folder/file restructuring logic based on filename dashes.
    - If no dash, filename becomes folder, file becomes 'index'.
    - Skip specified directories
    - Tracks copied and extra files.
    - 'casing' parameter: 'snake' for snake_case (default), 'pascal' for PascalCase.
    """
    src_path = Path(src_folder)
    dist_path = Path(dist_folder)
    copied_count = 0
    extra_files_count = 0

    if skip_dirs is None:
        skip_dirs = []

    # Ensure dist_folder exists
    dist_path.mkdir(parents=True, exist_ok=True)

    # Function to apply casing
    def apply_casing(name, case_type):
        if case_type == "snake":
            # Convert PascalCase to snake_case if present, then replace spaces/underscores with hyphens
            s1 = name.replace(" ", "-").replace("_", "-")
            s2 = ''.join(['-' + c.lower() if c.isupper() else c for c in s1]).lstrip('-')
            return s2.lower()
        elif case_type == "pascal":
            # Convert snake/kebab case to PascalCase
            return ''.join(word.capitalize() for word in name.replace("-", " ").replace("_", " ").split())
        else:
            return name # Default to original if casing is unknown

    # Keep track of all target files that are created/expected in dist_folder
    all_target_files = set()

    for file in src_path.rglob("*"):
        if not file.is_file():
            continue

        # Skip directories you want to ignore
        if any(skip in file.parts for skip in skip_dirs):
            continue

        # Get relative path and base filename
        rel_path = file.relative_to(src_path)
        base_name = rel_path.stem  # filename without extension

        folder_name_parts = []
        final_file_name = "index" # Default for files without dashes

        # Determine folder structure and final file name
        if '-' in base_name:
            # Split by all dashes for infinite nesting
            name_parts = [part.replace("_", "-") for part in base_name.split('-')] # Keep original case for now, apply casing later

            if not name_parts:
                continue

            # The last part is the file name
            final_file_name = name_parts[-1]
            # The preceding parts form the nested directory structure
            folder_name_parts = name_parts[:-1]
        else:
            # If no dash, the entire base_name becomes the primary folder
            folder_name_parts = [base_name.replace("_", "-")] # Use base_name for folder part


        # Apply casing to folder parts
        processed_folder_parts = [apply_casing(part, casing) for part in folder_name_parts]

        # Apply casing to the final file name
        processed_file_name = apply_casing(final_file_name, casing)


        # Set final extension
        final_ext = new_extension if new_extension else file.suffix
        if not final_ext.startswith("."):
            final_ext = "." + final_ext

        # Build target path
        target_dir = dist_path / Path(*processed_folder_parts)
        target_file = target_dir / f"{processed_file_name}{final_ext}"

        # Ensure destination directory exists
        target_dir.mkdir(parents=True, exist_ok=True)

        # Copy the file to new destination
        shutil.copy(file, target_file)
        print(f"📁 {file.name} → {target_file.relative_to(dist_path)}")
        copied_count += 1
        all_target_files.add(target_file) # Add copied files to our set of expected files

    print(f"\n✅ {copied_count} files processed from '{src_folder}' to '{dist_folder}'.")
