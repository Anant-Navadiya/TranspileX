import os
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
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.messages import Messenger
from transpilex.helpers.move_files import move_files
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json


class CakePHPConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=CAKEPHP_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / self.project_name
        self.project_assets_path = self.project_root / CAKEPHP_ASSETS_FOLDER
        self.project_pages_path = Path(self.project_root / "templates" / "Pages")
        self.project_element_path = Path(self.project_root / "templates" / "element")
        self.project_pages_controller_path = Path(self.project_root / "src" / "Controller" / "PagesController.php")
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

        empty_folder_contents(self.project_pages_path)

        change_extension_and_copy(CAKEPHP_EXTENSION, self.source_path, self.project_pages_path)

        self._convert(self.project_pages_path)

        partials_path = self.project_pages_path / 'partials'
        if partials_path.exists() and partials_path.is_dir():
            move_files(partials_path, self.project_element_path)
            self._convert(self.project_element_path)

        self._rename_hyphens_to_underscores()

        self._add_root_method_to_app_controller()

        self._patch_routes()

        copy_assets(self.assets_path, self.project_assets_path, preserve=CAKEPHP_ASSETS_PRESERVE)

        create_gulpfile_js(self.project_root, CAKEPHP_ASSETS_FOLDER)

        # update_package_json(self.source_path, self.project_root, self.project_name)

        Messenger.completed(f"Project '{self.project_name}' setup", str(self.project_root))

    def _convert(self, directory: Path):
        count = 0

        for file in directory.rglob("*.php"):
            content = file.read_text(encoding="utf-8")
            original_content = content

            if "@@include" not in content and ".html" not in content:
                continue

            # === Handle @@include with parameters ===
            def include_with_params(match):
                file_path = match.group(1).strip()
                param_json = match.group(2).strip()
                try:
                    params = json.loads(param_json)
                    php_array = "array(" + ", ".join(
                        [f'"{k}" => {json.dumps(v)}' for k, v in params.items()]
                    ) + ")"
                    view_name = Path(file_path).stem
                    return f'<?= $this->element("{view_name}", {php_array}) ?>'
                except json.JSONDecodeError as e:
                    Messenger.warning(f"[JSON Error] in file {file.name}: {e}")
                    return match.group(0)

            # === Handle @@include without parameters ===
            def include_no_params(match):
                view_name = Path(match.group(1).strip()).stem
                return f'<?= $this->element("{view_name}") ?>'

            # Replace @@include(...) with CakePHP includes
            content = re.sub(
                r"""@@include\(\s*["']([^"']+?\.html)["']\s*,\s*(\{[\s\S]*?\})\s*\)""",
                include_with_params,
                content,
                flags=re.DOTALL,
            )

            content = re.sub(
                r"""@@include\(\s*["']([^"']+?\.html)["']\s*\)""",
                include_no_params,
                content,
            )

            # Replace .html links and clean asset paths
            content = replace_html_links(content, '')
            content = clean_relative_asset_paths(content)

            if content != original_content:
                file.write_text(content, encoding="utf-8")
                Messenger.updated(f"Updated: {file}")
                count += 1

        Messenger.success(f"{count} files updated in: {directory}")

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

    def _rename_hyphens_to_underscores(self, ignore_list=None):
        if ignore_list is None:
            ignore_list = []

        for dirpath, dirnames, filenames in os.walk(self.project_pages_path, topdown=False):
            # Rename files
            for name in filenames:
                if name in ignore_list:
                    continue
                if "-" in name:
                    src = Path(dirpath) / name
                    dst_name = name.replace("-", "_")
                    if dst_name in ignore_list:
                        continue
                    dst = Path(dirpath) / dst_name
                    src.rename(dst)

            # Rename directories
            for name in dirnames:
                if name in ignore_list:
                    continue
                if "-" in name:
                    src = Path(dirpath) / name
                    dst_name = name.replace("-", "_")
                    if dst_name in ignore_list:
                        continue
                    dst = Path(dirpath) / dst_name
                    src.rename(dst)
