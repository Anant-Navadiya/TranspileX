import re
import json
import subprocess
from pathlib import Path

from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json


def convert_to_cakephp(dist_folder):
    """
    Replace @@include() statements with CakePHP-style $this->element() syntax.
    """
    dist_path = Path(dist_folder)
    count = 0

    for file in dist_path.rglob("*.php"):
        content = file.read_text(encoding="utf-8")
        original_content = content

        # Skip files without any @@include or .html reference
        if "@@include" not in content and ".html" not in content:
            continue

        def with_params(match):
            file_path = match.group(1).strip()
            param_json = match.group(2).strip()
            try:
                params = json.loads(param_json)
                php_array = "array(" + ", ".join(
                    [f'"{k}" => {json.dumps(v)}' for k, v in params.items()]
                ) + ")"
                view_name = Path(file_path).stem
                return f'<?= $this->element("{view_name}", {php_array}) ?>'
            except json.JSONDecodeError:
                return match.group(0)

        def no_params(match):
            view_name = Path(match.group(1).strip()).stem
            return f'<?= $this->element("{view_name}") ?>'

        content = re.sub(r"@@include\(['\"](.+?\.html)['\"]\s*,\s*(\{.*?\})\)", with_params, content)
        content = re.sub(r"@@include\(['\"](.+?\.html)['\"]\)", no_params, content)

        # replace .html with .php in anchor
        content = replace_html_links(content, '')

        # remove assets from links, scripts
        content = clean_relative_asset_paths(content)

        if content != original_content:
            file.write_text(content, encoding="utf-8")
            print(f"🔁 Updated CakePHP includes in: {file}")
            count += 1

    print(f"\n✅ {count} files updated with CakePHP includes.")


def add_root_method_to_app_controller(controller_path):
    app_controller = Path(controller_path)
    if not app_controller.exists():
        print(f"❌ File not found: {app_controller}")
        return

    content = app_controller.read_text(encoding="utf-8")
    if 'public function root(' in content:
        print("ℹ️ Method 'root' already exists in PagesController.")
        return

    method_code = """
    public function root($path): Response
    {
        try {
            return $this->render($path);
        } catch (MissingTemplateException $exception) {
            if (Configure::read('debug')) {
                throw $exception;
            }
            throw new NotFoundException();
        }
    }
"""
    updated = re.sub(r"^\}\s*$", method_code + "\n}", content, flags=re.MULTILINE)
    app_controller.write_text(updated, encoding="utf-8")
    print("✅ Added 'root' method to AppController.")


def patch_routes(project_path):
    routes_file = Path(project_path) / "config" / "routes.php"
    if not routes_file.exists():
        print(f"❌ routes.php not found in: {routes_file}")
        return

    content = routes_file.read_text(encoding="utf-8")
    original = "$builder->connect('/', ['controller' => 'Pages', 'action' => 'display', 'home']);"
    replacement = (
        "$builder->connect('/', ['controller' => 'Pages', 'action' => 'display', 'index']);\n"
        "        $builder->connect('/*', ['controller' => 'Pages', 'action' => 'root']);"
    )

    if original in content:
        routes_file.write_text(content.replace(original, replacement), encoding="utf-8")
        print("🔁 Updated routes.php with custom routing.")
    else:
        print("⚠️ Expected line not found. Skipping patch.")


def create_cakephp_project(project_name, source_folder, assets_folder):
    """
    1. Create a new CakePHP project under the 'cakephp/' directory.
    2. Copy all files from the source_folder to the new project's templates/Pages folder.
    3. Convert includes to CakePHP-style.
    4. Add root() method to PagesController.
    5. Patch routes
    6. Copy custom assets to webroot, preserving required files.
    """

    project_root = Path("cakephp") / project_name
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create CakePHP project
    print(f"📦 Creating CakePHP project at '{project_root}'...")
    try:
        subprocess.run(
            f'composer create-project --prefer-dist cakephp/app:~5.0 {project_root}',
            shell=True, check=True
        )
        print("✅ CakePHP project created.")
    except subprocess.CalledProcessError:
        print("❌ Composer failed. Ensure PHP and Composer are configured correctly.")
        return

    # Copy HTML/converted files to templates/Pages
    pages_path = project_root / "templates" / "Pages"
    pages_path.mkdir(parents=True, exist_ok=True)

    change_extension_and_copy('php', source_folder, pages_path)

    # Convert @@include syntax to CakePHP element includes
    print(f"\n🔧 Converting includes in '{pages_path}'...")
    convert_to_cakephp(pages_path)

    # Add root method to PagesController
    controller_path = project_root / "src" / "Controller" / "PagesController.php"
    add_root_method_to_app_controller(controller_path)

    # Patch routes
    patch_routes(project_root)

    # Copy assets to webroot while preserving required files
    assets_path = project_root / "webroot"
    copy_assets(assets_folder, assets_path, preserve=["index.php", ".htaccess"])

    # Create gulpfile.js
    create_gulpfile_js(project_root, './webroot')

    # Update dependencies
    update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")