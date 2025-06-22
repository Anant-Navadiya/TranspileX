import os
from pathlib import Path
import shutil


def change_extension_and_copy(new_extension, src_folder, dist_folder):
    """
     Recursively convert file extensions and copy to a dist folder, preserving structure.

     :param src_folder: Source directory path (default 'src')
     :param new_extension: New extension (e.g., 'php' or '.php')
     :param dist_folder: Output directory path (default 'dist')
     """
    src_path = Path(src_folder)
    dist_path = Path(dist_folder)

    if not src_path.exists() or not src_path.is_dir():
        print(f"❌ Source folder '{src_folder}' does not exist or is not a directory.")
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

            print(f"✅ {file} → {destination}")
            count += 1

    print(f"\n🎉 {count} files processed and saved in '{dist_folder}' with '{new_extension}' extension.")
