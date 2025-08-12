import re
import json
import subprocess
from pathlib import Path

from transpilex.config.base import CODEIGNITER_DESTINATION_FOLDER, CODEIGNITER_ASSETS_FOLDER, \
    CODEIGNITER_PROJECT_CREATION_COMMAND, CODEIGNITER_EXTENSION, CODEIGNITER_ASSETS_PRESERVE, \
    CODEIGNITER_GULP_ASSETS_PATH
from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.add_gulpfile import add_gulpfile
from transpilex.helpers.logs import Log
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.package_json import update_package_json


class CodeIgniterConverter:

    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(CODEIGNITER_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / CODEIGNITER_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "app" / "Views")
        self.project_partials_path = Path(self.project_views_path / "partials")
        self.project_home_controller_path = Path(self.project_root / "app" / "Controllers" / "Home.php")
        self.project_routes_path = Path(self.project_root / "app" / "Config" / "Routes.php")

        self.create_project()

    def create_project(self):

        Log.project_start(self.project_name)

        self.project_root.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(f'{CODEIGNITER_PROJECT_CREATION_COMMAND} {self.project_root}', shell=True, check=True)
            Log.success(f"Codeigniter project created successfully")
        except subprocess.CalledProcessError:
            Log.error(f"Codeigniter project creation failed")
            return

        change_extension_and_copy(CODEIGNITER_EXTENSION, self.source_path, self.project_views_path)

        self._convert()

        self._replace_partial_variables()

        self._add_home_controller()

        self._patch_routes()

        copy_assets(self.assets_path, self.project_assets_path, preserve=CODEIGNITER_ASSETS_PRESERVE)

        if self.include_gulp:
            add_gulpfile(self.project_root, CODEIGNITER_GULP_ASSETS_PATH)
            add_plugins_file(self.source_path, self.project_root)
            update_package_json(self.source_path, self.project_root, self.project_name)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):

        count = 0

        for file in self.project_views_path.rglob("*.php"):
            if file.is_file():
                content = file.read_text(encoding="utf-8")
                original_content = content

                # Handle @@include with JSON-like parameters
                def include_with_params(match):
                    file_path = match.group(1).strip()
                    param_json_str = match.group(2).strip()

                    # Normalize sloppy JSON
                    fixed = re.sub(r",\s*(?=[}\]])", "", param_json_str)  # remove trailing commas
                    fixed = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', fixed)  # single quotes → double
                    fixed = re.sub(r"([{\s,])'([^']+)'\s*:", r'\1"\2":', fixed)  # single-quoted keys → double

                    try:
                        params = json.loads(fixed)
                        php_array = "array(" + ", ".join(
                            [f'"{k}" => {json.dumps(v)}' for k, v in params.items()]
                        ) + ")"
                        view_name = Path(file_path).stem
                        return f'<?php echo view("{view_name}", {php_array}) ?>'
                    except json.JSONDecodeError as e:
                        Log.warning(f"[JSON Error] in file {file.name}: {e}")
                        return match.group(0)

                # @@include with PHP array parameters
                def include_with_array_params(match):
                    file_path = match.group(1).strip()
                    php_array_str = match.group(2).strip()
                    view_name = Path(file_path).stem
                    return f'<?php echo view("{view_name}", {php_array_str}) ?>'

                # Handle @@include without parameters
                def include_no_params(match):
                    file_path = match.group(1).strip()
                    view_name = Path(file_path).stem
                    return f"<?= $this->include('{view_name}') ?>"

                # Replace includes
                content = re.sub(
                    r"""@@include\(['"]([^"']+)['"]\s*,\s*(\{[\s\S]*?\})\s*\)""",
                    include_with_params,
                    content,
                    flags=re.DOTALL
                )
                content = re.sub(
                    r"""@@include\(['"]([^"']+)['"]\s*,\s*(array\(.*?\))\s*\)""",
                    include_with_array_params,
                    content,
                    flags=re.DOTALL
                )
                content = re.sub(
                    r"""@@include\(['"]([^"']+)['"]\s*\)""",
                    include_no_params,
                    content
                )

                # Clean up HTML links and asset paths
                content = replace_html_links(content, '')
                content = clean_relative_asset_paths(content)

                if content != original_content:
                    file.write_text(content, encoding="utf-8")
                    Log.converted(str(file))
                    count += 1

        Log.info(f"{count} files converted in {self.project_views_path}")

    def _add_home_controller(self):
        try:
            if self.project_home_controller_path.exists():
                with open(self.project_home_controller_path, "w", encoding="utf-8") as f:
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
                throw \CodeIgniter\Exceptions\PageNotFoundException::forPageNotFound();
            }
        } else {
            echo 'Path Not Found.';
        }
    }
}
        ''')
                Log.created(f"root method in HomeController.php")
            else:
                Log.warning(f"HomeController not found at {self.project_home_controller_path}")
        except Exception as e:
            Log.error(f"Failed to update HomeController.php: {e}")

    def _patch_routes(self):

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
        self.project_routes_path.write_text(new_content, encoding="utf-8")
        Log.updated(f"Routes.php with custom routing")

    def _replace_partial_variables(self):
        """
        Replace @@<var> with short echo '<?= $<var> ?>' across all PHP files.
        Skips control/directive tokens like @@if and @@include.
        """
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_partials_path.rglob(f"*{CODEIGNITER_EXTENSION}"):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            new_content = pattern.sub(r'<?= $\1 ?>', content)
            if new_content != content:
                file.write_text(new_content, encoding="utf-8")
                Log.updated(str(file))
                count += 1

        if count:
            Log.info(f"{count} files updated in {self.project_partials_path}")