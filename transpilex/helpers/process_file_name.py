import os

def process_file_name_nested(file_name):
    """Extract nested folder path, PascalCase file name, and model name from a kebab-case filename."""
    pre, _ = os.path.splitext(file_name)
    parts = pre.split('-')

    if len(parts) == 1:
        # No nesting
        folder_path = parts[0].capitalize()
        file_name = "Index"
    else:
        folder_path = os.path.join(*[part.lower() for part in parts[:-1]])
        file_name = parts[-1].capitalize()

    model_name = f"{file_name}Model"
    return pre, folder_path, file_name, model_name
