import re
import json
import subprocess
from pathlib import Path

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, CAKEPHP_DESTINATION_FOLDER, \
    CAKEPHP_ASSETS_FOLDER, CAKEPHP_EXTENSION, CAKEPHP_PROJECT_CREATION_COMMAND, CAKEPHP_ASSETS_PRESERVE
from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.messages import Messenger
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json


class CakePHPConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=CAKEPHP_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / CAKEPHP_ASSETS_FOLDER
        self.project_pages_path = Path(self.project_root / "templates" / "Pages")
        self.project_pages_controller_path = Path(self.project_root / "controllers" / "PagesController.php")
        self.project_routes_path = Path(self.project_root / "config" / "routes.php")

        self.create_project()

    def create_project(self):

        Messenger.info(f"Creating CakePHP project at: '{self.project_root}'...")

        self.project_root.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(f'{CAKEPHP_PROJECT_CREATION_COMMAND} {self.project_root}', shell=True, check=True)
            Messenger.success(f"CakePHP project created.")
        except subprocess.CalledProcessError:
            Messenger.error(f"CakePHP project creation failed.")
            return

        change_extension_and_copy(CAKEPHP_EXTENSION, self.source_path, self.project_pages_path)

        self._convert()

        self.project_pages_path.mkdir(parents=True, exist_ok=True)

        self._add_root_method_to_app_controller()

        self._patch_routes()

        copy_assets(self.assets_path, self.project_assets_path, preserve=CAKEPHP_ASSETS_PRESERVE)

        create_gulpfile_js(self.project_root, CAKEPHP_ASSETS_FOLDER)

        # update_package_json(self.source_path, self.project_root, self.project_name)

        Messenger.completed(f"Project '{self.project_name}' setup", str(self.project_root))

    def _convert(self):
        count = 0

        for file in self.project_pages_path.rglob("*.php"):
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
                Messenger.updated(f"Updated includes in: {file}")
                count += 1

        Messenger.success(f"{count} files updated with CakePHP includes.")

    def _add_root_method_to_app_controller(self):

        if not self.project_pages_controller_path.exists():
            Messenger.error(f"File not found: {self.project_pages_controller_path}")
            return

        content = self.project_pages_controller_path.read_text(encoding="utf-8")
        if 'public function root(' in content:
            Messenger.info("Method 'root' already exists in PagesController.")
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
        self.project_pages_controller_path.write_text(updated, encoding="utf-8")
        Messenger.success("Added 'root' method to AppController.")

    def _patch_routes(self):

        if not self.project_routes_path.exists():
            Messenger.error(f"File not found: {self.project_routes_path}")
            return

        content = self.project_routes_path.read_text(encoding="utf-8")
        original = "$builder->connect('/', ['controller' => 'Pages', 'action' => 'display', 'home']);"
        replacement = (
            "$builder->connect('/', ['controller' => 'Pages', 'action' => 'display', 'index']);\n"
            "        $builder->connect('/*', ['controller' => 'Pages', 'action' => 'root']);"
        )

        if original in content:
            self.project_routes_path.write_text(content.replace(original, replacement), encoding="utf-8")
            Messenger.updated("Updated routes.php with custom routing.")
        else:
            Messenger.warning("Expected line not found. Skipping patch.")