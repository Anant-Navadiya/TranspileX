import json
import re
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
import shutil

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, BLAZOR_ASSETS_FOLDER, BLAZOR_DESTINATION_FOLDER, \
    BLAZOR_PROJECT_CREATION_COMMAND, BLAZOR_EXTENSION, BLAZOR_GULP_ASSETS_PATH
from transpilex.helpers import change_extension_and_copy, copy_assets
from transpilex.helpers.change_extension import change_extension
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.add_gulpfile import add_gulpfile
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.logs import Log
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.restructure_files import apply_casing


class BlazorConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=BLAZOR_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name.title()
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / self.project_name
        self.project_assets_path = self.project_root / BLAZOR_ASSETS_FOLDER
        self.project_pages_path = Path(self.project_root / "Components" / "Pages")

        self.project_layout_path = Path(self.project_root / "Components" / "Layout")
        self.project_partials_path = Path(self.project_layout_path / "Partials")

        self.create_project()

    def create_project(self):
        Log.info(f"Creating Blazor project at: '{self.project_root}'...")

        self.project_root.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(f'{BLAZOR_PROJECT_CREATION_COMMAND} {self.project_name}', shell=True, check=True,
                           cwd=self.project_root.parent)

            Log.success(f"Blazor project created.")

            subprocess.run(
                f'dotnet new sln -n {self.project_name}',
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

            Log.success(".sln file created successfully.")

        except subprocess.CalledProcessError:
            Log.error(f"Blazor project creation failed.")
            return

        empty_folder_contents(self.project_pages_path)

        self._convert()

        empty_folder_contents(self.project_layout_path)

        self._move_partials()

        copy_assets(self.assets_path, self.project_assets_path)

        add_gulpfile(self.project_root, BLAZOR_GULP_ASSETS_PATH)

        Log.completed(f"Project '{self.project_name}' setup", str(self.project_root))

    def _convert(self, skip_dirs=["partials"], casing="pascal"):

        copied_count = 0

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

            script_tags = soup.find_all('script')

            js_import_path = None
            # Find first script tag with src starting with /js, assets/js or ./js
            for tag in script_tags:
                src = tag.get('src', '')
                if src.startswith('/js') or src.startswith('assets/js') or src.startswith('./js'):
                    js_import_path = src
                    break  # take first matching

            # Remove all scripts and link tags anyway
            for tag in script_tags:
                tag.decompose()
            for tag in soup.find_all('link', rel='stylesheet'):
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

            top_lines = f"""@page "{route_path}"
    @rendermode InteractiveServer
    @inject IJSRuntime JsRuntime;

    """
            if is_body_content:
                # Assuming project name is self.project_name, adjust casing if needed
                top_lines += f"""@using {self.project_name}.Components.Layout
            @layout BaseLayout

            """

            else:
                top_lines += "\n"

            if js_import_path:
                # Fix the path if needed - remove leading slash to make it relative for import
                if js_import_path.startswith('/'):
                    js_import_path = '.' + js_import_path

                end_lines = f"""
    @code {{
        private IJSObjectReference? _module;

        protected override async Task OnAfterRenderAsync(bool firstRender)
        {{
            if (firstRender)
            {{
                _module = await JsRuntime.InvokeAsync<IJSObjectReference>("import", "{js_import_path}");
                await JsRuntime.InvokeVoidAsync("");
                await JsRuntime.InvokeVoidAsync("loadConfig");
                await JsRuntime.InvokeVoidAsync("loadApps");
            }}
        }}
    }}
    """
            else:
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

            razor_content = f"{top_lines}{main_content}\n{end_lines}"

            razor_content = clean_relative_asset_paths(razor_content)
            razor_content = self._convert_partial_include_to_blazor(razor_content)
            razor_content = replace_html_links(razor_content, '')

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(razor_content.strip() + "\n")

            print(f"✅ Created: {target_file.relative_to(self.project_pages_path)}")
            copied_count += 1

        print(f"\n✨ {copied_count} .razor files generated from HTML sources.")

    def _generate_viewbag_code(self, data: dict):
        if not data:
            return ""

        lines = []
        for key, val in data.items():
            val_str = str(val).replace('"', '\\"')
            lines.append(f'ViewBag.{key} = "{val_str}";')

        return "@{\n    " + "\n    ".join(lines) + "\n}"

    def _convert_partial_include_to_blazor(self, content: str) -> str:
        # Regex to capture @@include call with JSON params
        pattern = re.compile(
            r'@@include\(\s*"(?P<path>[^"]+)"\s*,\s*(?P<json>{.*?})\s*\)',
            re.DOTALL
        )

        def replacer(match):
            path = match.group("path")
            json_str = match.group("json")

            # Extract component name from partial filename, e.g. page-title.html => PageTitle
            partial_file = Path(path).stem
            component_name = ''.join(word.capitalize() for word in partial_file.split('-'))

            # Try to parse JSON params
            try:
                params = json.loads(json_str)
            except json.JSONDecodeError:
                # If JSON invalid, just return original string (or handle error as needed)
                return match.group(0)

            # Convert keys and values to Blazor component attributes
            attr_list = []
            for key, val in params.items():
                # Escape quotes inside val if string
                if isinstance(val, str):
                    val_escaped = val.replace('"', '&quot;')
                    attr_list.append(f'{key}="{val_escaped}"')
                else:
                    attr_list.append(f'{key}="{val}"')

            attrs = ' '.join(attr_list)

            # Compose Blazor component tag
            return f"<{component_name} {attrs} />"

        return pattern.sub(replacer, content)

    def _move_partials(self):
        partials_dir = Path(self.source_path / "partials")
        change_extension(BLAZOR_EXTENSION, partials_dir, self.project_partials_path)
