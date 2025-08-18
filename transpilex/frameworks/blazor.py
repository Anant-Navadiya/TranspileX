import json
import re
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
import os

from transpilex.config.base import BLAZOR_ASSETS_FOLDER, BLAZOR_DESTINATION_FOLDER, \
    BLAZOR_PROJECT_CREATION_COMMAND, BLAZOR_EXTENSION, BLAZOR_GULP_ASSETS_PATH, SLN_FILE_CREATION_COMMAND
from transpilex.helpers import copy_assets
from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.casing import to_pascal_case
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.gulpfile import add_gulpfile
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.logs import Log
from transpilex.helpers.package_json import update_package_json
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.restructure_files import apply_casing
from transpilex.helpers.validations import folder_exists


class BlazorConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True,
                 plugins_config: bool = True):
        self.project_name = project_name.title()
        self.source_path = Path(source_path)
        self.destination_path = Path(BLAZOR_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp
        self.plugins_config = plugins_config

        self.project_root = self.destination_path / self.project_name
        self.project_assets_path = self.project_root / BLAZOR_ASSETS_FOLDER
        self.project_pages_path = Path(self.project_root / "Components" / "Pages")
        self.project_layout_path = Path(self.project_root / "Components" / "Layout")
        self.project_partials_path = Path(self.project_layout_path / "Partials")

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        try:

            self.project_root.parent.mkdir(parents=True, exist_ok=True)

            subprocess.run(f'{BLAZOR_PROJECT_CREATION_COMMAND} {self.project_name}', shell=True, check=True,
                           cwd=self.project_root.parent)

            Log.success(f"Blazor project created successfully")

            subprocess.run(
                f'{SLN_FILE_CREATION_COMMAND} {self.project_name}',
                cwd=self.project_root.parent,
                shell=True,
                check=True
            )

            sln_file = f"{self.project_name}.sln"

            subprocess.run(
                f'dotnet sln {sln_file} add {Path(self.project_name) / self.project_name}.csproj',
                cwd=self.project_root.parent,
                shell=True,
                check=True
            )

            Log.info(".sln file created successfully")

        except subprocess.CalledProcessError:
            Log.error(f"Blazor project creation failed")
            return

        copy_assets(self.assets_path, self.project_assets_path)

        empty_folder_contents(self.project_pages_path)

        self._convert()

        empty_folder_contents(self.project_layout_path)

        self._copy_partials()

        if self.include_gulp:
            add_gulpfile(self.project_root, BLAZOR_GULP_ASSETS_PATH, self.plugins_config)
            update_package_json(self.source_path, self.project_root, self.project_name)

        if self.include_gulp and self.plugins_config:
            add_plugins_file(self.source_path, self.project_root)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self, skip_dirs=["partials"], casing="pascal"):
        count = 0
        if skip_dirs is None:
            skip_dirs = []

        for file in self.source_path.rglob("*.html"):
            relative_file_path_str = str(file.relative_to(self.source_path)).replace("\\", "/")
            if not file.is_file() or any(skip in relative_file_path_str for skip in skip_dirs):
                continue

            relative_path = file.relative_to(self.source_path)
            with open(file, "r", encoding="utf-8") as f:
                raw_html = f.read()

            soup = BeautifulSoup(raw_html, "html.parser")
            is_partial = "partials" in file.parts

            js_import_paths = []
            excluded_paths = ["plugins/", "vendors/", "libs/"]

            for tag in soup.find_all('script'):
                src = tag.get('src')
                if src:
                    if not any(excluded in src for excluded in excluded_paths):
                        js_import_paths.append(src)
                else:
                    script_content = tag.string
                    if script_content and "new Date().getFullYear()" in script_content:
                        tag.replace_with("@DateTime.Now.Year")

            for tag in soup.find_all(['script', 'link']):
                tag.decompose()

            if is_partial:
                main_content = soup.decode_contents().strip()
                is_body_content = False
            else:
                content_block = soup.find(attrs={"data-content": True})
                if content_block:
                    main_content = content_block.decode_contents().strip()
                    is_body_content = False
                elif soup.body:
                    main_content = soup.body.decode_contents().strip()
                    is_body_content = True
                else:
                    main_content = soup.decode_contents().strip()
                    is_body_content = False

            base_name = file.stem
            if '-' in base_name:
                name_parts = [part.replace("_", "-") for part in base_name.split('-')]
                final_file_name = name_parts[-1]
                file_based_folders = name_parts[:-1]
            else:
                file_based_folders = [base_name.replace("_", "-")]
                final_file_name = "index"

            relative_folder_parts = list(relative_path.parent.parts)
            combined_folder_parts = relative_folder_parts + file_based_folders
            processed_folder_parts = [apply_casing(p, casing) for p in combined_folder_parts]
            processed_file_name = apply_casing(final_file_name, casing)

            final_ext = ".razor"
            target_dir = self.project_pages_path / Path(*processed_folder_parts)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / f"{processed_file_name}{final_ext}"
            route_path = "/" + base_name.lower().replace("_", "-")

            top_lines = ""
            end_lines = ""

            if js_import_paths:
                top_lines = f"""@page "{route_path}"
@rendermode InteractiveServer
@implements IAsyncDisposable
@inject IJSRuntime JsRuntime;

"""
                import_statements = []
                load_function_calls = []

                for path_str in js_import_paths:

                    clean_path_str = path_str.lstrip('/')

                    primary_path = self.source_path / clean_path_str
                    fallback_path = self.source_path / 'assets' / clean_path_str

                    original_file_path = None
                    if primary_path.is_file():
                        original_file_path = primary_path
                    elif fallback_path.is_file():
                        original_file_path = fallback_path

                    if original_file_path:
                        function_name, import_path = self._wrap_and_copy_js_file(original_file_path)
                        if function_name and import_path:
                            import_statements.append(
                                f'_modules.Add(await JsRuntime.InvokeAsync<IJSObjectReference>("import", "./{import_path}"));')
                            load_function_calls.append(f'await JsRuntime.InvokeVoidAsync("{function_name}");')
                    else:
                        Log.warning(f"Could not find JS source file for {path_str}")

                imports_code = "\n                    ".join(import_statements)
                load_calls_code = "\n                    ".join(load_function_calls)

                end_lines = f"""
@code {{
    private List<IJSObjectReference> _modules = new();

    protected override async Task OnAfterRenderAsync(bool firstRender)
    {{
        if (firstRender)
        {{
            try
            {{
                {imports_code}
                {load_calls_code}
                await JsRuntime.InvokeVoidAsync("loadConfig");
                await JsRuntime.InvokeVoidAsync("loadApps");
            }}
            catch (Exception ex)
            {{
                Console.WriteLine($"Error during JS interop: {{ex.Message}}");
            }}
        }}
    }}

    async ValueTask IAsyncDisposable.DisposeAsync()
    {{
        foreach (var module in _modules)
        {{
            if (module is not null)
            {{
                await module.DisposeAsync();
            }}
        }}
    }}
}}
    """
            else:
                top_lines = f"""@page "{route_path}"
@rendermode InteractiveServer
@inject IJSRuntime JsRuntime;

"""
            end_lines = """
@code {
    protected override async Task OnAfterRenderAsync(bool firstRender)
    {
        if (firstRender)
        {
            await JsRuntime.InvokeVoidAsync("loadConfig");
            await JsRuntime.InvokeVoidAsync("loadApps");
        }
    }
}
    """
            if is_body_content:
                top_lines += f"""@using {self.project_name}.Components.Layout
@layout BaseLayout

"""
            else:
                top_lines += "\n"

            razor_content = f"{top_lines}{main_content}\n{end_lines}"
            razor_content = clean_relative_asset_paths(razor_content)
            razor_content = self._convert_partial_include_to_blazor(razor_content)
            razor_content = replace_html_links(razor_content, '')

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(razor_content.strip() + "\n")

            Log.converted(str(target_file))
            count += 1

        Log.info(f"{count} files converted in {self.project_pages_path}")

    def _generate_viewbag_code(self, data: dict):
        if not data:
            return ""

        lines = []
        for key, val in data.items():
            val_str = str(val).replace('"', '\\"')
            lines.append(f'ViewBag.{key} = "{val_str}";')

        return "@{\n    " + "\n    ".join(lines) + "\n}"

    def _convert_partial_include_to_blazor(self, content: str) -> str:
        """
        Finds @@include statements and converts them to Blazor components.

        Specifically targets 'page-title.html' and 'app-pagetitle.html' to
        create a generic <PageBreadcrumb /> component with dynamic attributes.
        """
        pattern = re.compile(
            r'@@include\(\s*[\'"](?P<path>[^\'"]+)[\'"]\s*,\s*(?P<json>{.*?})\s*\)',
            re.DOTALL
        )

        def replacer(match):
            path = match.group("path")
            json_str = match.group("json")
            partial_file_name = Path(path).name

            # --- KEY LOGIC: Check for target partials ---
            if partial_file_name in ["page-title.html", "app-pagetitle.html"]:
                component_name = "PageBreadcrumb"
            else:
                # Fallback for other partials (e.g., menu.html, title-meta.html)
                partial_stem = Path(path).stem
                component_name = ''.join(word.capitalize() for word in partial_stem.replace('app-', '').split('-'))

            # --- Sanitize JSON to handle common formatting issues ---
            # 1. Replace newlines within the string to handle multi-line values
            json_str_single_line = json_str.replace('\n', ' ')
            # 2. Remove trailing commas before the closing brace '}'
            sanitized_json_str = re.sub(r',\s*(?=})', '', json_str_single_line)

            try:
                params = json.loads(sanitized_json_str)
            except json.JSONDecodeError:
                Log.warning(f"Could not parse JSON for partial '{path}'.")
                return match.group(0)

            # Generate attributes dynamically from any key-value pairs
            attr_list = []
            for key, val in params.items():
                # Convert key to PascalCase
                pascal_key = key[0].upper() + key[1:] if key else ""

                if isinstance(val, str):
                    val_escaped = val.replace('"', '&quot;')
                    attr_list.append(f'{pascal_key}="{val_escaped}"')
                else:  # Handles bools, numbers, etc.
                    attr_list.append(f'{pascal_key}="{str(val).lower() if isinstance(val, bool) else val}"')

            attrs = ' '.join(attr_list)

            return f"<{component_name} {attrs} />"

        return pattern.sub(replacer, content)

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
                # processed_content, _ = self._process_includes(content, [])

                # Also clean asset paths within the partial
                processed_content = clean_relative_asset_paths(content)
                processed_content = replace_html_links(processed_content, '')

                # Determine the new _PascalCase.cshtml filename
                pascal_stem = to_pascal_case(source_file.stem)
                new_filename = f"{pascal_stem}{BLAZOR_EXTENSION}"
                destination_file = self.project_partials_path / new_filename

                # Write the processed content to the new file
                with open(destination_file, "w", encoding="utf-8") as f:
                    f.write(processed_content)

    def _wrap_and_copy_js_file(self, original_js_path: Path):
        """
        Reads a JS file, wraps it, and saves it to the Blazor project's
        wwwroot, stripping the 'assets' prefix to maintain a clean structure.
        """
        if not original_js_path.is_file():
            Log.warning(f"JS source file not found, skipping: {original_js_path}")
            return None, None

        try:

            # Get the script's path relative to the source project root.
            relative_path = original_js_path.relative_to(self.source_path)
            relative_path_str = str(relative_path)

            # If the path starts with 'assets/', remove it.
            if relative_path_str.startswith('assets/'):
                # The new path will be 'scripts/pages/dashboard.js'
                final_relative_path = Path(relative_path_str[len('assets/'):])
            else:
                # If it doesn't, use the path as is.
                final_relative_path = relative_path

            # The destination is now correctly calculated without the 'assets' folder.
            destination_file = self.project_assets_path / final_relative_path
            destination_file.parent.mkdir(parents=True, exist_ok=True)

            # The rest of the function remains the same
            file_stem = original_js_path.stem
            parts = file_stem.split('-')
            pascal_case_stem = "".join(word.capitalize() for word in parts)
            function_name = f"load{pascal_case_stem}"

            with open(original_js_path, "r", encoding="utf-8") as f:
                original_content = f.read()

            wrapped_content = f"""
window.{function_name} = function () {{
{original_content}
}};
    """
            with open(destination_file, "w", encoding="utf-8") as f:
                f.write(wrapped_content.strip())

            # The import path for Blazor will now be correct
            import_path = final_relative_path.as_posix()
            return function_name, import_path

        except Exception as e:
            Log.error(f"An unexpected error occurred while processing '{original_js_path}': {e}")
            return None, None
