import re
import json
import subprocess
from pathlib import Path

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, CODEIGNITER_DESTINATION_FOLDER, CODEIGNITER_ASSETS_FOLDER, \
    CODEIGNITER_PROJECT_CREATION_COMMAND, CODEIGNITER_EXTENSION, CODEIGNITER_ASSETS_PRESERVE, \
    CODEIGNITER_GULP_ASSETS_PATH
from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.messages import Messenger
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json

class CodeIgniterConverter:

    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=CODEIGNITER_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / CODEIGNITER_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "app" / "Views")
        self.project_element_path = Path(self.project_root / "templates" / "element")
        self.project_pages_controller_path = Path(self.project_root / "src" / "Controller" / "PagesController.php")
        self.project_routes_path = Path(self.project_root / "config" / "routes.php")

        self.create_project()

    def create_project(self):

        Messenger.info(f"Creating Codeigniter project at: '{self.project_root}'...")

        self.project_root.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(f'{CODEIGNITER_PROJECT_CREATION_COMMAND} {self.project_root}', shell=True, check=True)
            Messenger.success(f"Codeigniter project created.")
        except subprocess.CalledProcessError:
            Messenger.error(f"Codeigniter project creation failed.")
            return

        change_extension_and_copy(CODEIGNITER_EXTENSION, self.source_path, self.project_views_path)

        copy_assets(self.assets_path, self.project_assets_path, preserve=CODEIGNITER_ASSETS_PRESERVE)

        create_gulpfile_js(self.project_root, CODEIGNITER_GULP_ASSETS_PATH)

        # update_package_json(self.source_path, self.project_root, self.project_name)

        Messenger.completed(f"Project '{self.project_name}' setup", str(self.project_root))


def convert_to_codeigniter(dist_folder):
    """
    Replace @@include() with CodeIgniter-style view syntax in .php files.
    Correctly handles both JSON and 'array(...)' parameters, and optional '.html' in paths.
    Ensures all .php files are processed for HTML link and asset path cleaning.
    """
    dist_path = Path(dist_folder)
    count = 0

    for file in dist_path.rglob("*.php"):
        if file.is_file():
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # --- Helper functions for replacements ---

            # Handles @@include with JSON parameters: {"key": "value"}
            def include_with_json_params(match):
                file_path = match.group(1).strip()
                param_json_str = match.group(2).strip()
                try:
                    params = json.loads(param_json_str)
                    php_array = "array(" + ", ".join(
                        [f'"{k}" => {json.dumps(v)}' for k, v in params.items()]
                    ) + ")"
                    view_name = Path(file_path).stem  # Get base name without extension
                    return f'<?php echo view("{view_name}", {php_array}) ?>'
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON decode error in @@include for file {file.name}: {e}\nContent: {match.group(0)}")
                    return match.group(0)  # Return original match on error

            # Handles @@include with PHP array parameters: array("key" => "value")
            def include_with_array_params(match):
                file_path = match.group(1).strip()
                php_array_str = match.group(2).strip()  # Capture the full PHP array string

                view_name = Path(file_path).stem  # Get base name without extension

                # Directly insert the captured PHP array string into the view() call
                return f'<?php echo view("{view_name}", {php_array_str}) ?>'

            # Handles @@include without parameters
            def include_no_params(match):
                file_path = match.group(1).strip()
                view_name = Path(file_path).stem  # Get base name without extension
                return f"<?= $this->include('{view_name}') ?>"

            # --- Apply replacements in order ---

            # 1. Replace @@include with JSON parameters (optional .html in path)
            # Match path: ([^"']+) - matches any characters except quotes (making .html optional)
            # Match params: (\{[\s\S]*?\}) - matches JSON object, including newlines
            content = re.sub(
                r"""@@include\(['"]([^"']+)['"]\s*,\s*(\{[\s\S]*?\})\s*\)""",
                include_with_json_params,
                content,
                flags=re.DOTALL
            )

            # 2. Replace @@include with PHP array parameters (optional .html in path)
            # Match path: ([^"']+) - matches any characters except quotes (making .html optional)
            # Match params: (array\(.*?\)) - matches array(...)
            content = re.sub(
                r"""@@include\(['"]([^"']+)['"]\s*,\s*(array\(.*?\))\s*\)""",
                include_with_array_params,
                content,
                flags=re.DOTALL
            )

            # 3. Replace @@include without parameters (optional .html in path)
            # Match path: ([^"']+) - matches any characters except quotes (making .html optional)
            content = re.sub(
                r"""@@include\(['"]([^"']+)['"]\s*\)""",
                include_no_params,
                content
            )

            # ALWAYS replace .html links and clean asset paths for every file
            # (The problematic 'continue' condition has been removed from here as discussed previously)
            content = replace_html_links(content, '')
            content = clean_relative_asset_paths(content)

            if content != original_content:
                with open(file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"🔁 Updated CodeIgniter syntax, links, and/or assets in: {file}")
                count += 1

    print(f"\n✅ {count} files processed and updated for CodeIgniter compatibility.")


def add_home_controller(controller_path):
    # Inject custom controller logic into Home.php
    try:
        if controller_path.exists():
            with open(controller_path, "w", encoding="utf-8") as f:
                f.write(r'''<?php

    namespace App\Controllers;

    class Home extends BaseController
    {
        public function index()
        {
            return view('index');
        }

        public function root($path = '')
        {
            if ($path !== '') {
                if (@file_exists(APPPATH . 'Views/' . $path . '.php')) {
                    return view($path);
                } else {
                    throw \\CodeIgniter\\Exceptions\\PageNotFoundException::forPageNotFound();
                }
            } else {
                echo 'Path Not Found.';
            }
        }
    }
    ''')
            print(f"✅ Custom HomeController.php written to: {controller_path}")
        else:
            print(f"⚠️ HomeController not found at {controller_path}")
    except Exception as e:
        print(f"❌ Failed to update HomeController.php: {e}")


def patch_routes(project_path):
    routes_file = Path(project_path) / "app" / "Config" / "Routes.php"
    new_content = """<?php

    use CodeIgniter\\Router\\RouteCollection;

    $routes = \\Config\\Services::routes();

    $routes->setDefaultNamespace('App\\Controllers');
    $routes->setDefaultController('Home');
    $routes->setDefaultMethod('index');

    /**
     * @var RouteCollection $routes
     */
    $routes->get('/', 'Home::index');
    $routes->get('/(:any)', 'Home::root/$1');
    """
    routes_file.write_text(new_content, encoding="utf-8")
    print(f"🔁 Updated Routes.php with custom routing.")


def create_codeigniter_project(project_name, source_folder, assets_folder):
    """
    1. Create a new Codeigniter project using Composer.
    2. Copy all files from the source_folder to the new project's templates/Pages folder.
    3. Convert the includes to Codeigniter-style using convert_to_codeigniter().
    4. Add HomeController.php to the Controllers folder.
    5. Patch routes.
    6. Copy custom assets to public, preserving required files.
    """

    project_root = Path("codeigniter") / project_name
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create the Codeigniter project using Composer
    print(f"📦 Creating Codeigniter project '{project_root}'...")
    try:
        subprocess.run(
            f'composer create-project codeigniter4/appstarter {project_root}',
            shell=True,
            check=True
        )
        print("✅ Codeigniter project created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create Codeigniter project. Make sure Composer and PHP are set up correctly.")
        return

    # Copy source files into templates/Pages/ as .php files
    pages_path = project_root / "app" / "Views"
    pages_path.mkdir(parents=True, exist_ok=True)

    change_extension_and_copy('php', source_folder, pages_path)

    # Convert @@include to Codeigniter syntax in all .php files inside templates/Pages/
    print(f"\n🔧 Converting includes in '{pages_path}'...")
    convert_to_codeigniter(pages_path)

    # Add Home Controller
    controller_path = Path(project_root) / "app" / "Controllers" / "Home.php"
    add_home_controller(controller_path)

    # Patch routes
    patch_routes(project_root)

    # Copy assets to webroot while preserving required files
    assets_path = project_root / "public"
    copy_assets(assets_folder, assets_path, preserve=["index.php", ".htaccess", "manifest.json", "robots.txt"])

    # Create gulpfile.js
    create_gulpfile_js(project_root, './public')

    # Update dependencies
    update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
