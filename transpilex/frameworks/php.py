import re
import json
from pathlib import Path

from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json

from transpilex.config.base import PHP_FOLDER, PHP_SRC_FOLDER, PHP_EXTENSION, PHP_ASSETS_FOLDER, PHP_GULP_ASSET_PATH


def convert_to_php(dist_folder):
    """
    Converts HTML-style @@include syntax in files to PHP include syntax in the specified folder.

    Supported patterns:
    - @@include('./partials/header.html')
      → <?php include('partials/header.php'); ?>

    - @@include('./partials/page-title.html', {"title": "Dashboard", "subtitle": "Home"})
      → <?php $title = "Dashboard"; $subtitle = "Home"; include('partials/page-title.php'); ?>
    """
    dist_path = Path(dist_folder)
    count = 0

    for file in dist_path.rglob("*"):
        if file.is_file() and file.suffix == PHP_EXTENSION:
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # Skip files with no relevant patterns
            if "@@include" not in content and ".html" not in content:
                continue

            # Replace includes with parameters
            def include_with_params(match):
                path = match.group(1)
                json_str = match.group(2)
                try:
                    params = json.loads(json_str)
                    # Convert JSON to PHP variable declarations
                    php_vars = ''.join([f"${k} = {json.dumps(v)}; " for k, v in params.items()])
                    php_path = path.replace(".html", PHP_EXTENSION)
                    return f"<?php {php_vars}include('{php_path}'); ?>"
                except json.JSONDecodeError:
                    return match.group(0)  # Leave original if JSON is malformed

            content = re.sub(
                r"""@@include\(['"](.+?\.html)['"]\s*,\s*(\{.*?\})\s*\)""",
                include_with_params,
                content
            )

            # Replace includes without parameters
            content = re.sub(
                r"""@@include\(['"](.+?\.html)['"]\)""",
                lambda m: f"<?php include('{m.group(1).replace('.html', PHP_EXTENSION)}'); ?>",
                content
            )

            # Replace anchor .html links with .php equivalents
            content = replace_html_links(content, PHP_EXTENSION)

            if content != original_content:
                with open(file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"🔁 Replaced includes in: {file}")
                count += 1

    print(f"\n✅ Replaced includes in {count} PHP files in '{dist_folder}'.")


def create_php_project(project_name, source_folder, assets_folder):
    """
    Bootstraps a new PHP project with converted templates and assets.

    Steps:
    1. Create project folder: php/<project_name>/src/
    2. Copy HTML files (converted to PHP) into the src folder
    3. Convert @@include directives to PHP include() syntax
    4. Copy assets into the src/assets folder
    5. Generate a Gulp file for asset handling
    6. Update package.json with project dependencies and metadata
    """
    project_root = Path(PHP_FOLDER) / project_name
    project_src = project_root / PHP_SRC_FOLDER

    print(f"📦 Creating PHP project at: '{project_src}'...")
    project_src.mkdir(parents=True, exist_ok=True)

    # Step 1: Copy HTML files and convert extension to .php
    change_extension_and_copy(PHP_EXTENSION, source_folder, project_src)

    # Step 2: Replace all @@include directives with PHP includes
    convert_to_php(project_src)

    # Step 3: Copy assets
    assets_path = project_src / PHP_ASSETS_FOLDER
    copy_assets(assets_folder, assets_path)

    # Step 4: Generate gulpfile.js for asset compilation
    create_gulpfile_js(project_root, PHP_GULP_ASSET_PATH)

    # Step 5: Update or create package.json with project metadata
    update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
