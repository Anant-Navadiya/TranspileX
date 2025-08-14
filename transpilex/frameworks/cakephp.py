import os
import re
import json
import subprocess
from pathlib import Path

from transpilex.config.base import CAKEPHP_DESTINATION_FOLDER, \
    CAKEPHP_ASSETS_FOLDER, CAKEPHP_EXTENSION, CAKEPHP_PROJECT_CREATION_COMMAND, CAKEPHP_ASSETS_PRESERVE, \
    CAKEPHP_GULP_ASSETS_PATH
from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.gulpfile import add_gulpfile
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.logs import Log
from transpilex.helpers.move_files import move_files
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.package_json import update_package_json
from transpilex.helpers.validations import folder_exists


class CakePHPConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True,
                 plugins_config: bool = True):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(CAKEPHP_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp
        self.plugins_config = plugins_config

        self.project_root = self.destination_path / self.project_name
        self.project_assets_path = self.project_root / CAKEPHP_ASSETS_FOLDER
        self.project_pages_path = Path(self.project_root / "templates" / "Pages")
        self.project_partials_path = Path(self.project_pages_path / "partials")
        self.project_element_path = Path(self.project_root / "templates" / "element")
        self.project_pages_controller_path = Path(self.project_root / "src" / "Controller" / "PagesController.php")
        self.project_routes_path = Path(self.project_root / "config" / "routes.php")

        self.project_layout_path = Path(self.project_root / "templates" / "layout" / "default.php")

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        self.project_root.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(f'{CAKEPHP_PROJECT_CREATION_COMMAND} {self.project_root}', shell=True, check=True)
            Log.success(f"CakePHP project created successfully")
        except subprocess.CalledProcessError:
            Log.error(f"CakePHP project creation failed")
            return

        empty_folder_contents(self.project_pages_path)

        change_extension_and_copy(CAKEPHP_EXTENSION, self.source_path, self.project_pages_path)

        self._convert()

        if self.project_partials_path.exists() and self.project_partials_path.is_dir():
            move_files(self.project_partials_path, self.project_element_path)

        self._replace_partial_variables()

        self._rename_hyphens_to_underscores()

        self._add_root_method_to_app_controller()

        self._patch_routes()

        self._replace_default_layout()

        copy_assets(self.assets_path, self.project_assets_path, preserve=CAKEPHP_ASSETS_PRESERVE)

        if self.include_gulp:
            add_gulpfile(self.project_root, CAKEPHP_GULP_ASSETS_PATH, self.plugins_config)
            update_package_json(self.source_path, self.project_root, self.project_name)

        if self.include_gulp and self.plugins_config:
            add_plugins_file(self.source_path, self.project_root)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):
        count = 0

        for file in self.project_pages_path.rglob("*.php"):
            content = file.read_text(encoding="utf-8")
            original_content = content

            if "@@include" not in content and ".html" and "assets" not in content:
                continue

            # === Handle @@include with parameters ===
            def include_with_params(match):
                file_path = match.group(1).strip()
                param_json = match.group(2).strip()

                # Normalize sloppy JSON: remove trailing commas; convert single-quoted strings to double-quoted
                fixed = re.sub(r",\s*(?=[}\]])", "", param_json)  # trailing commas
                fixed = re.sub(r"'([^'\\]*(?:\\.[^'\\]*)*)'", r'"\1"', fixed)  # 'value' -> "value"
                # single-quoted keys -> double-quoted keys
                fixed = re.sub(r"([{\s,])'([^']+)'\s*:", r'\1"\2":', fixed)

                try:
                    params = json.loads(fixed)
                    php_array = "array(" + ", ".join(
                        [f'"{k}" => {json.dumps(v)}' for k, v in params.items()]
                    ) + ")"
                    view_name = Path(file_path).stem
                    return f'<?= $this->element("{view_name}", {php_array}) ?>'
                except json.JSONDecodeError as e:
                    Log.warning(f"[JSON Error] in file {file.name}: {e}")
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
                flags=re.DOTALL,
            )

            # Replace .html links and clean asset paths
            content = replace_html_links(content, '')
            content = clean_relative_asset_paths(content)

            if content != original_content:
                file.write_text(content, encoding="utf-8")
                Log.converted(str(file))
                count += 1

        Log.info(f"{count} files converted in {self.project_pages_path}")

    def _add_root_method_to_app_controller(self):

        if not self.project_pages_controller_path.exists():
            Log.error(f"File not found: {self.project_pages_controller_path}")
            return

        content = self.project_pages_controller_path.read_text(encoding="utf-8")
        if 'public function root(' in content:
            Log.warning("Method 'root' already exists in PagesController")
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
        Log.created("root method in AppController")

    def _patch_routes(self):

        if not self.project_routes_path.exists():
            Log.error(f"File not found: {self.project_routes_path}")
            return

        content = self.project_routes_path.read_text(encoding="utf-8")
        original = "$builder->connect('/', ['controller' => 'Pages', 'action' => 'display', 'home']);"
        replacement = (
            "$builder->connect('/', ['controller' => 'Pages', 'action' => 'display', 'index']);\n"
            "        $builder->connect('/*', ['controller' => 'Pages', 'action' => 'root']);"
        )

        if original in content:
            self.project_routes_path.write_text(content.replace(original, replacement), encoding="utf-8")
            Log.updated("routes.php with custom routing")
        else:
            Log.warning("Expected line not found. Skipping patch")

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

    def _replace_partial_variables(self):
        """
        Replace @@<var> with short echo '<?= $<var> ?>' across all PHP files.
        Skips control/directive tokens like @@if and @@include.
        """
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_element_path.rglob(f"*{CAKEPHP_EXTENSION}"):
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
            Log.info(f"{count} files updated in {self.project_element_path}")

    def _replace_default_layout(self):
        layout_path = self.project_layout_path
        layout_path.parent.mkdir(parents=True, exist_ok=True)

        new_content = """<?= $this->Flash->render() ?>
<?= $this->fetch('content') ?>
"""

        layout_path.write_text(new_content, encoding="utf-8")
        Log.updated(str(layout_path))
