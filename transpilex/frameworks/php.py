import re
import json
from pathlib import Path

from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json


def convert_to_php(dist_folder):
    """
    Replace @@include() HTML syntax with PHP include statements in all files inside dist_folder.

    Handles both:
    - @@include('./partials/menu.html')
    - @@include('./partials/page-title.html', {"title": "X", "subtitle": "Y"})
    """
    dist_path = Path(dist_folder)
    count = 0

    for file in dist_path.rglob("*"):
        if file.is_file() and file.suffix == '.php':
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # Skip files without any @@include or .html reference
            if "@@include" not in content and ".html" not in content:
                continue

            # Convert @@include('./file.html', {"key": "value"}) → PHP
            def include_with_params(match):
                path = match.group(1)
                json_str = match.group(2)
                try:
                    params = json.loads(json_str)
                    php_vars = ''.join([f"${k} = {json.dumps(v)}; " for k, v in params.items()])
                    php_path = path.replace('.html', '.php')
                    return f"<?php {php_vars}include('{php_path}'); ?>"
                except json.JSONDecodeError:
                    return match.group(0)  # leave as is if invalid

            content = re.sub(r"""@@include\(['"](.+?\.html)['"]\s*,\s*(\{.*?\})\s*\)""", include_with_params, content)

            # Convert @@include('./file.html') → <?php include('file.php'); ?>
            content = re.sub(
                r"""@@include\(['"](.+?\.html)['"]\)""",
                lambda m: f"<?php include('{m.group(1).replace('.html', '.php')}'); ?>",
                content
            )

            # replace .html with .php in anchor
            content = replace_html_links(content, '.php')

            if content != original_content:
                with open(file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"🔁 Replaced includes in: {file}")
                count += 1

    print(f"\n✅ Replaced includes in {count} PHP files in '{dist_folder}'.")


def create_php_project(project_name, source_folder, assets_folder):
    """
    1. Create a new PHP project under the 'php/project_name/src' directory.
    2. Copy all source HTML files (converted to PHP) into that folder.
    3. Convert @@include to PHP include syntax.
    4. Copy assets into the same src folder.
    """

    project_root = Path("php") / project_name
    project_src = project_root / "src"

    print(f"📦 Creating PHP project at: '{project_src}'...")
    project_src.mkdir(parents=True, exist_ok=True)

    # Copy HTML -> PHP to src
    change_extension_and_copy("php", source_folder, project_src)

    # Replace @@include with PHP include() in .php files
    convert_to_php(project_src)

    # Copy assets
    assets_path = project_src / "assets"
    copy_assets(assets_folder, assets_path)

    # Create gulpfile.js
    create_gulpfile_js(project_root, './src/assets')

    # Update dependencies
    update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_src}")
