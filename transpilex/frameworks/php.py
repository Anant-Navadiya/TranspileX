import re
import json
from pathlib import Path

from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.messages import Messenger
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json

from transpilex.config.base import PHP_SRC_FOLDER, PHP_EXTENSION, PHP_ASSETS_FOLDER, PHP_GULP_ASSETS_PATH, \
    SOURCE_PATH, PHP_DESTINATION_FOLDER, ASSETS_PATH


class PHPConverter:

    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=PHP_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):

        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / project_name
        self.project_src_path = self.project_root / PHP_SRC_FOLDER
        self.project_assets_path = self.project_src_path / PHP_ASSETS_FOLDER

        self.project_src_path.mkdir(parents=True, exist_ok=True)

        self.create_project()

    def create_project(self):

        Messenger.info(f"Creating PHP project at: '{self.project_src_path}'...")

        change_extension_and_copy(PHP_EXTENSION, self.source_path, self.project_src_path)

        self._convert()

        copy_assets(self.assets_path, self.project_assets_path)

        create_gulpfile_js(self.project_root, PHP_GULP_ASSETS_PATH)

        # update_package_json(self.source_path, self.project_root, self.project_name)

        Messenger.completed(f"Project '{self.project_name}' setup", str(self.project_root))

    def _convert(self):
        count = 0

        for file in self.project_src_path.rglob("*"):
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
                        php_vars = ''.join([f"${k} = {json.dumps(v)}; " for k, v in params.items()])
                        php_path = path.replace(".html", PHP_EXTENSION)
                        return f"<?php {php_vars}include('{php_path}'); ?>"
                    except json.JSONDecodeError as e:
                        Messenger.warning(f"[JSON Error] in file {file.name}: {e}")
                        return match.group(0)

                # Replace includes with parameters
                content = re.sub(
                    r"""@@include\(\s*["'](.+?\.html)["']\s*,\s*(\{[\s\S]*?\})\s*\)""",
                    include_with_params,
                    content
                )

                # Replace includes without parameters
                content = re.sub(
                    r"""@@include\(\s*['"](.+?\.html)['"]\s*\)""",
                    lambda m: f"<?php include('{m.group(1).replace('.html', PHP_EXTENSION)}'); ?>",
                    content
                )

                # Replace anchor .html links with .php equivalents
                content = replace_html_links(content, PHP_EXTENSION)

                if content != original_content:
                    with open(file, "w", encoding="utf-8") as f:
                        f.write(content)
                    Messenger.replaced(file)
                    count += 1

        Messenger.success(f"Replaced includes in {count} PHP files in '{self.project_src_path}'.")
