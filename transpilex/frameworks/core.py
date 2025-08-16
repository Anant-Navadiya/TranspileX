import json
import re
import os
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.config.base import CORE_DESTINATION_FOLDER, CORE_PROJECT_CREATION_COMMAND, SLN_FILE_CREATION_COMMAND, \
    CORE_EXTENSION, CORE_ASSETS_FOLDER, CORE_GULP_ASSETS_PATH, CORE_ADDITIONAL_EXTENSION
from transpilex.helpers import copy_assets
from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.casing import to_pascal_case
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.gulpfile import add_gulpfile
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.logs import Log
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.restructure_files import apply_casing
from transpilex.helpers.package_json import update_package_json
from transpilex.helpers.validations import folder_exists


class CoreConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True,
                 plugins_config: bool = True):
        self.project_name = project_name.title()
        self.source_path = Path(source_path)
        self.destination_path = Path(CORE_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp
        self.plugins_config = plugins_config

        self.project_root = self.destination_path / self.project_name
        self.project_assets_path = self.project_root / CORE_ASSETS_FOLDER
        self.project_pages_path = self.project_root / "Pages"
        self.project_partials_path = self.project_pages_path / "Shared" / "Partials"

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        self.project_root.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                f'{CORE_PROJECT_CREATION_COMMAND} {self.project_name}', cwd=self.project_root.parent,
                shell=True, check=True)

            Log.success("Core project created successfully")

            subprocess.run(
                f'{SLN_FILE_CREATION_COMMAND} {self.project_name}', cwd=self.project_root.parent, shell=True,
                check=True)

            sln_file = f"{self.project_name}.sln"

            subprocess.run(
                f'dotnet sln {sln_file} add {Path(self.project_name) / self.project_name}.csproj',
                cwd=self.project_root.parent, shell=True, check=True)

            Log.info(".sln file created successfully")


        except subprocess.CalledProcessError:
            Log.error("Core project creation failed")
            return

        empty_folder_contents(self.project_pages_path, skip=['_ViewStart.cshtml', '_ViewImports.cshtml'])

        self._copy_partials()

        self._convert(skip_dirs=['partials'])

        self._add_additional_extension_files(skip_paths=['_ViewStart.cshtml', '_ViewImports.cshtml', 'Shared'])

        self._replace_partial_variables()

        copy_assets(self.assets_path, self.project_assets_path)

        if self.include_gulp:
            add_gulpfile(self.project_root, CORE_GULP_ASSETS_PATH, self.plugins_config)
            update_package_json(self.source_path, self.project_root, self.project_name)

        if self.include_gulp and self.plugins_config:
            add_plugins_file(self.source_path, self.project_root)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self, skip_dirs=None, casing="pascal"):
        count = 0
        if skip_dirs is None:
            skip_dirs = ['partials']

        # Define which partials are allowed to set the page's ViewBag properties
        page_title_partials = ["page-title.html", "app-pagetitle.html", "title-meta.html", "app-meta-title.html"]

        for file in self.source_path.rglob("*.html"):
            relative_file_path_str = str(file.relative_to(self.source_path)).replace("\\", "/")
            if not file.is_file() or any(skip in relative_file_path_str for skip in skip_dirs):
                continue

            with open(file, "r", encoding="utf-8") as f:
                raw_html = f.read()

            # Process all includes and extract page-title data at the same time
            processed_html, viewbag_data = self._process_includes(raw_html, page_title_partials)

            if not viewbag_data:
                Log.warning(
                    f"No ViewBag data extracted for page: {file.name}")

            soup = BeautifulSoup(processed_html, "html.parser")

            # ... (the rest of your logic for finding scripts, links, and content block) ...
            all_script_tags = soup.find_all('script')
            link_tags = soup.find_all('link', rel='stylesheet')

            scripts_to_move = []
            # Define the exact text of the script you want to exclude
            script_to_exclude = "document.write(new Date().getFullYear())"

            for tag in all_script_tags:
                # Check if the tag's text content matches the one to exclude
                if tag.get_text(strip=True) == script_to_exclude:
                    # If it matches, do nothing. Leave it in the main content.
                    pass
                else:
                    # For ALL other scripts (inline or external), add them to the move list.
                    scripts_to_move.append(tag)

            scripts_content = "\n    ".join([str(tag) for tag in scripts_to_move])
            styles_content = "\n    ".join([str(tag) for tag in link_tags])

            # Decompose only the tags that have been moved.
            tags_to_decompose = scripts_to_move + link_tags
            for tag in tags_to_decompose:
                tag.decompose()

            content_block = soup.find(attrs={"data-content": True})
            if content_block:
                main_content = content_block.decode_contents().strip()
            elif soup.body:
                main_content = soup.body.decode_contents().strip()
            else:
                main_content = soup.decode_contents().strip()

            # ... (the rest of your logic for determining file names and paths) ...
            base_name = file.stem
            if '-' in base_name:
                name_parts = [part.replace("_", "-") for part in base_name.split('-')]
                final_file_name = name_parts[-1]
                file_based_folders = name_parts[:-1]
            else:
                file_based_folders = [base_name.replace("_", "-")]
                final_file_name = "index"

            relative_path = file.relative_to(self.source_path)
            relative_folder_parts = list(relative_path.parent.parts)
            combined_folder_parts = relative_folder_parts + file_based_folders
            processed_folder_parts = [apply_casing(p, casing) for p in combined_folder_parts]
            processed_file_name = apply_casing(final_file_name, casing)

            target_dir = self.project_pages_path / Path(*processed_folder_parts)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / f"{processed_file_name}{CORE_EXTENSION}"
            route_path = "/" + base_name.lower().replace("_", "-")

            # Generate ViewBag code from the extracted data
            if not viewbag_data.get("Title"):
                viewbag_data["Title"] = processed_file_name  # Fallback title

            viewbag_code = self._generate_viewbag_code(viewbag_data)

            # ... (your logic for generating the final cshtml_content string) ...
            cshtml_content = f"""@page \"{route_path}\"
@model TEMP_NAMESPACE.{processed_file_name}Model

{viewbag_code}

@section styles
{{
    {styles_content}
}}

{main_content}

@section scripts
{{
    {scripts_content}
}}"""

            cshtml_content = clean_relative_asset_paths(cshtml_content)
            cshtml_content = replace_html_links(cshtml_content, '')

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(cshtml_content.strip() + "\n")

            Log.converted(str(target_file))
            count += 1

        Log.info(f"{count} files converted in {self.project_pages_path}")

    def _process_includes(self, content: str, page_title_partials: list[str]):
        """
        Processes all @@include directives in a given string.
        ...
        """
        viewbag_data = {}

        pattern = re.compile(r'@@include\(\s*["\'](.*?)["\']\s*(?:,\s*({.*?}))?\s*\)', re.DOTALL)

        def replacer(match):
            partial_path_str = match.group(1)
            json_str = match.group(2)

            partial_path = Path(partial_path_str)
            partial_filename = partial_path.name
            partial_stem = partial_path.stem

            if partial_filename in page_title_partials and json_str:
                try:
                    # ---> ADDED QUOTE NORMALIZATION LINE <---
                    # Convert all single quotes to double quotes to handle both styles
                    normalized_json = json_str.replace("'", '"')

                    # This regex finds all "key": "value" pairs, ignoring formatting issues.
                    kv_pattern = re.compile(r'"([^"]+)"\s*:\s*"([^"]*)"')
                    matches = kv_pattern.findall(normalized_json)

                    if not matches:
                        Log.warning(f"Could not extract any key-value pairs from {partial_filename}")

                    # Add all found pairs to the viewbag_data dictionary
                    for key, value in matches:
                        viewbag_data[to_pascal_case(key)] = value.strip()

                except Exception as e:
                    # A general catch-all just in case of unexpected errors
                    Log.error(f"An unexpected error occurred while parsing JSON for {partial_filename}. Reason: {e}")
                    Log.info(f"Problematic string: {json_str}")

            # Convert the partial's filename to the Razor convention (_PascalCase.cshtml)
            pascal_stem = to_pascal_case(partial_stem)
            razor_partial_name = f"_{pascal_stem}{CORE_EXTENSION}"

            # Return the Razor syntax for a partial view
            return f'@await Html.PartialAsync("~/Pages/Shared/Partials/{razor_partial_name}")'

        processed_content = pattern.sub(replacer, content)
        return processed_content, viewbag_data

    def _extract_include_variables(self, content: str, partial_name="page-title.html"):
        """
        Extract all variables from an @@include for the given partial_name (supports ./partials, ../partials, partials).

        Returns:
            tuple(dict, str): (dictionary of PascalCase keys and values, content with include replaced by Razor partial)
        """
        pattern = (
                r'@@include\(\s*["\'](?:\.{1,2}/)?partials/' + re.escape(partial_name) + r'["\']\s*,\s*({.*?})\s*\)'
        )

        match = re.search(pattern, content, flags=re.DOTALL)
        if match:
            json_str = match.group(1)
            try:
                json_fixed = json_str.replace("'", '"')
                data_raw = json.loads(json_fixed)
            except json.JSONDecodeError:
                data_raw = {}

            data_pascal = {to_pascal_case(k): v for k, v in data_raw.items()}

            replacement = '@await Html.PartialAsync("~/Pages/Shared/Partials/_PageTitle.cshtml")'
            updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

            return data_pascal, updated_content

        return {}, content

    def _generate_viewbag_code(self, data: dict):
        if not data:
            return ""

        lines = []
        for key, val in data.items():
            val_str = str(val).replace('"', '\\"')
            lines.append(f'ViewBag.{key} = "{val_str}";')

        return "@{\n    " + "\n    ".join(lines) + "\n}"

    def _set_content(self, namespace, model_name):
        return f"""using Microsoft.AspNetCore.Mvc.RazorPages;

namespace {namespace}
{{
    public class {model_name} : PageModel
    {{
        public void OnGet() {{ }}
    }}
}}"""

    def _add_additional_extension_files(self, additional_extension=CORE_ADDITIONAL_EXTENSION, skip_paths=None):
        generated_count = 0

        new_extension = additional_extension if additional_extension.startswith(".") else f".{additional_extension}"

        pascal_app_name = apply_casing(self.project_name, "pascal")

        if skip_paths is None:
            skip_paths = []

        for file in self.project_pages_path.rglob(f"*{CORE_EXTENSION}"):
            relative_file_path_str = str(file.relative_to(self.project_pages_path)).replace("\\", "/")
            if any(skip in relative_file_path_str for skip in skip_paths):
                continue

            file_name = file.stem
            folder_parts = file.relative_to(self.project_pages_path).parent.parts
            folder_path = file.parent

            model_name = f"{file_name}Model"
            namespace = f"{pascal_app_name}.Pages" + (
                '.' + '.'.join([apply_casing(p, 'pascal') for p in folder_parts]) if folder_parts else "")

            new_file_path = folder_path / f"{file_name}{new_extension}"
            content = self._set_content(namespace, model_name)

            with open(file, "r+", encoding="utf-8") as f:
                view = f.read()
                view = view.replace("TEMP_NAMESPACE", namespace)
                f.seek(0)
                f.write(view)
                f.truncate()

            try:
                with open(new_file_path, "w", encoding="utf-8") as f:
                    f.write(content.strip() + "\n")
                Log.created(str(new_file_path.relative_to(self.project_pages_path)))
                generated_count += 1
            except IOError as e:
                Log.error(f"Error writing {new_file_path}: {e}")

        Log.info(f"{generated_count} {new_extension} files generated")

    def _copy_partials(self):
        """
        Copies and processes partials from the source folder.
        It renames them to _PascalCase.cshtml, and processes their content
        for nested includes.
        """
        self.project_partials_path.mkdir(parents=True, exist_ok=True)
        partials_source = self.source_path / "partials"

        if partials_source.exists() and partials_source.is_dir():
            for filename in os.listdir(partials_source):
                source_file = partials_source / filename
                if not source_file.is_file():
                    continue

                # Read the original partial's content
                with open(source_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Process its content for nested includes.
                # We pass an empty list because partials should not set the page's ViewBag.
                processed_content, _ = self._process_includes(content, [])

                # Also clean asset paths within the partial
                processed_content = clean_relative_asset_paths(processed_content)
                processed_content = replace_html_links(processed_content, '')

                # Determine the new _PascalCase.cshtml filename
                pascal_stem = to_pascal_case(source_file.stem)
                new_filename = f"_{pascal_stem}{CORE_EXTENSION}"
                destination_file = self.project_partials_path / new_filename

                # Write the processed content to the new file
                with open(destination_file, "w", encoding="utf-8") as f:
                    f.write(processed_content)

    def _replace_partial_variables(self):
        """
        Replace @@<var> with short echo '<?= $<var> ?>' across all PHP files.
        Skips control/directive tokens like @@if and @@include.
        """
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_partials_path.rglob(f"*{CORE_EXTENSION}"):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            new_content = pattern.sub(r'@\1', content)
            if new_content != content:
                file.write_text(new_content, encoding="utf-8")
                Log.updated(str(file))
                count += 1

        if count:
            Log.info(f"{count} files updated in {self.project_partials_path}")
