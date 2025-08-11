import re
import json
from pathlib import Path

from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.change_extension import change_extension_and_copy
from transpilex.helpers.copy_assets import copy_assets
from transpilex.helpers.add_gulpfile import add_gulpfile
from transpilex.helpers.messages import Messenger
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json

from transpilex.config.base import PHP_SRC_FOLDER, PHP_EXTENSION, PHP_ASSETS_FOLDER, PHP_GULP_ASSETS_PATH, \
    PHP_DESTINATION_FOLDER


class PHPConverter:

    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True):

        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(PHP_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp

        self.project_root = self.destination_path / project_name
        self.project_src_path = self.project_root / PHP_SRC_FOLDER
        self.project_assets_path = self.project_src_path / PHP_ASSETS_FOLDER
        self.project_partials_path = self.project_src_path / "partials"

        self.project_src_path.mkdir(parents=True, exist_ok=True)

        self.create_project()

    def create_project(self):

        Messenger.project_start(self.project_name)

        change_extension_and_copy(PHP_EXTENSION, self.source_path, self.project_src_path)

        self._convert()

        self._replace_partial_variables()

        copy_assets(self.assets_path, self.project_assets_path)

        if self.include_gulp:
            add_gulpfile(self.project_root, PHP_GULP_ASSETS_PATH)
            add_plugins_file(self.source_path, self.project_root)
            update_package_json(self.source_path, self.project_root, self.project_name)

        Messenger.project_end(self.project_name, str(self.project_root))

    def _convert(self):

        count = 0

        # Iterate only destination files (*.php)
        for dest_file in self.project_src_path.rglob(f"*{PHP_EXTENSION}"):
            if not dest_file.is_file():
                continue

            # Read as UTF-8; silently skip if binary/non-UTF8
            try:
                with open(dest_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except (UnicodeDecodeError, OSError):
                continue

            original_content = content

            # Only work if includes or .html links are present
            if "@@include" not in content and ".html" not in content:
                continue

            # --- helpers ---
            def to_php_path(path: str) -> str:
                return path[:-5] + PHP_EXTENSION if path.endswith(".html") else path + PHP_EXTENSION

            # Replace includes WITH parameters (allow missing .html)
            def include_with_params(match):
                path = match.group(1).strip()
                json_str = match.group(2)

                fixed_json_str = re.sub(r",\s*(?=[}\]])", "", json_str)
                fixed_json_str = re.sub(r"'([^']*)'", r'"\1"', fixed_json_str)

                try:
                    params = json.loads(fixed_json_str)
                    php_vars = ''.join([f"${k} = {json.dumps(v)}; " for k, v in params.items()])
                    php_path = to_php_path(path)
                    return f"<?php {php_vars}include('{php_path}'); ?>"
                except json.JSONDecodeError as e:
                    Messenger.warning(f"[JSON Error] in file {dest_file.name}: {e}")
                    return match.group(0)

            # Replace includes WITHOUT parameters (allow missing .html)
            def include_without_params(m):
                path = m.group(1).strip()
                return f"<?php include('{to_php_path(path)}'); ?>"

            # Do replacements
            content = re.sub(
                r"""@@include\(\s*["'](.+?)["']\s*,\s*(\{[\s\S]*?\})\s*\)""",
                include_with_params,
                content
            )

            content = re.sub(
                r"""@@include\(\s*['"](.+?)['"]\s*\)""",
                include_without_params,
                content
            )

            # Replace anchor .html links with .php equivalents
            content = replace_html_links(content, PHP_EXTENSION)

            if content != original_content:
                try:
                    with open(dest_file, "w", encoding="utf-8") as f:
                        f.write(content)
                    Messenger.converted(str(dest_file))
                    count += 1
                except Exception as e:
                    Messenger.error(f"Failed to write {dest_file}: {e}")
            else:
                Messenger.warning(f"File was skipped (no patterns matched): {dest_file}")

        Messenger.info(f"{count} files converted in {self.project_src_path}")

    def _replace_partial_variables(self):
        """
        Scans all created PHP files for template syntax like '@@variable'
        and replaces it with the equivalent PHP echo statement.
        """

        count = 0
        for file in self.project_partials_path.rglob(f"*{PHP_EXTENSION}"):
            if not file.is_file():
                continue

            try:
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()
            except (UnicodeDecodeError, OSError):
                continue

            original_content = content

            # Replace standalone variables: @@var, but ignore @@if
            content = re.sub(r'@@(?!if\b)(\w+)', r'<?php echo ($\1); ?>', content)

            if content != original_content:
                with open(file, "w", encoding="utf-8") as f:
                    f.write(content)
                Messenger.updated(str(file))
                count += 1

        if count > 0:
            Messenger.info(f"{count} files updated in {self.project_partials_path}")
