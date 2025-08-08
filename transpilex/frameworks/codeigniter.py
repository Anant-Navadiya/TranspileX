import re
import json
import subprocess
from pathlib import Path

from transpilex.config.base import CODEIGNITER_DESTINATION_FOLDER, CODEIGNITER_ASSETS_FOLDER, \
    CODEIGNITER_PROJECT_CREATION_COMMAND, CODEIGNITER_EXTENSION, CODEIGNITER_ASSETS_PRESERVE, \
    CODEIGNITER_GULP_ASSETS_PATH
from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.add_gulpfile import add_gulpfile
from transpilex.helpers.messages import Messenger
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json


class CodeIgniterConverter:

    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(CODEIGNITER_DESTINATION_FOLDER)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / CODEIGNITER_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "app" / "Views")
        self.project_home_controller_path = Path(self.project_root / "app" / "Controllers" / "Home.php")
        self.project_routes_path = Path(self.project_root / "app" / "Config" / "Routes.php")

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

        self._convert()

        self._add_home_controller()

        self._patch_routes()

        copy_assets(self.assets_path, self.project_assets_path, preserve=CODEIGNITER_ASSETS_PRESERVE)

        add_gulpfile(self.project_root, CODEIGNITER_GULP_ASSETS_PATH)

        # update_package_json(self.source_path, self.project_root, self.project_name)

        Messenger.completed(f"Project '{self.project_name}' setup", str(self.project_root))

    def _convert(self):

        count = 0

        for file in self.project_views_path.rglob("*.php"):
            if file.is_file():
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()

                original_content = content

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
                        Messenger.warning(
                            f"JSON decode error in @@include for file {file.name}: {e}\nContent: {match.group(0)}")
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

                # Replace @@include with JSON parameters (optional .html in path)
                # Match path: ([^"']+) - matches any characters except quotes (making .html optional)
                # Match params: (\{[\s\S]*?\}) - matches JSON object, including newlines
                content = re.sub(
                    r"""@@include\(['"]([^"']+)['"]\s*,\s*(\{[\s\S]*?\})\s*\)""",
                    include_with_json_params,
                    content,
                    flags=re.DOTALL
                )

                # Replace @@include with PHP array parameters (optional .html in path)
                # Match path: ([^"']+) - matches any characters except quotes (making .html optional)
                # Match params: (array\(.*?\)) - matches array(...)
                content = re.sub(
                    r"""@@include\(['"]([^"']+)['"]\s*,\s*(array\(.*?\))\s*\)""",
                    include_with_array_params,
                    content,
                    flags=re.DOTALL
                )

                # Replace @@include without parameters (optional .html in path)
                # Match path: ([^"']+) - matches any characters except quotes (making .html optional)
                content = re.sub(
                    r"""@@include\(['"]([^"']+)['"]\s*\)""",
                    include_no_params,
                    content
                )

                content = replace_html_links(content, '')
                content = clean_relative_asset_paths(content)

                if content != original_content:
                    with open(file, "w", encoding="utf-8") as f:
                        f.write(content)
                    Messenger.updated(f"CodeIgniter syntax, links, and/or assets in: {file}")
                    count += 1

        Messenger.success(f"{count} files processed and updated for CodeIgniter compatibility.")

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
                        throw \\CodeIgniter\\Exceptions\\PageNotFoundException::forPageNotFound();
                    }
                } else {
                    echo 'Path Not Found.';
                }
            }
        }
        ''')
                Messenger.success(f"Custom HomeController.php written to: {self.project_home_controller_path}")
            else:
                Messenger.warning(f"HomeController not found at {self.project_home_controller_path}")
        except Exception as e:
            Messenger.error(f"Failed to update HomeController.php: {e}")

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
        Messenger.updated(f"Routes.php with custom routing.")
