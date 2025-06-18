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


def convert_to_codeigniter(dist_folder):
    """
    Replace @@include() with CodeIgniter-style view syntax in .php files.

    Examples:
    - @@include('./partials/head-css.html')
      → <?= $this->include('partials/head-css') ?>

    - @@include('./partials/page-title.html', {"title": "Calendar"})
      → <?php echo view("partials/page-title", array("title" => "Calendar")) ?>
    """
    dist_path = Path(dist_folder)
    count = 0

    for file in dist_path.rglob("*"):
        if file.is_file() and file.suffix == ".php":
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content

            # Skip files without any @@include or .html reference
            if "@@include" not in content and ".html" not in content:
                continue

            # Handle includes with parameters
            def with_params(match):
                html_path = match.group(1).strip()
                param_json = match.group(2).strip()
                try:
                    params = json.loads(param_json)
                    php_array = "array(" + ", ".join(
                        [f'"{k}" => {json.dumps(v)}' for k, v in params.items()]
                    ) + ")"
                    view_path = html_path.replace(".html", "").lstrip("./")
                    return f'<?php echo view("{view_path}", {php_array}) ?>'
                except json.JSONDecodeError:
                    return match.group(0)  # keep unchanged if JSON invalid

            # Handle plain includes (no parameters)
            def no_params(match):
                html_path = match.group(1).strip()
                view_path = html_path.replace(".html", "").lstrip("./")
                return f"<?= $this->include('{view_path}') ?>"

            # First, replace includes with parameters
            content = re.sub(
                r"""@@include\(['"](.+?\.html)['"]\s*,\s*(\{.*?\})\s*\)""", with_params, content
            )

            # Then, replace includes without parameters
            content = re.sub(
                r"""@@include\(['"](.+?\.html)['"]\)""", no_params, content
            )

            # replace .html
            content = replace_html_links(content, '')

            # remove assets from links, scripts
            content = clean_relative_asset_paths(content)

            if content != original_content:
                with open(file, "w", encoding="utf-8") as f:
                    f.write(content)
                print(f"🔁 Updated CodeIgniter includes in: {file}")
                count += 1

    print(f"\n✅ {count} files updated with CodeIgniter includes.")


def add_home_controller(controller_path):
    # Inject custom controller logic into Home.php
    try:
        if controller_path.exists():
            with open(controller_path, "w", encoding="utf-8") as f:
                f.write('''<?php

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
