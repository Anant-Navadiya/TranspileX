import re
import json
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from shutil import move, which

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, LARAVEL_DESTINATION_FOLDER, LARAVEL_ASSETS_FOLDER, \
    LARAVEL_EXTENSION, LARAVEL_RESOURCES_PRESERVE
from transpilex.helpers import copy_assets
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.messages import Messenger
from transpilex.helpers.restructure_files import restructure_files


class LaravelConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=LARAVEL_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / LARAVEL_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "resources" / "views")
        self.project_routes_path = Path(self.project_root / "routes" / "web.php")
        self.project_controllers_path = Path(self.project_root / "app" / "Http" / "Controllers")
        self.project_route_controller_path = Path(self.project_controllers_path / "RoutingController.php")

        self.create_project()

    def create_project(self):
        Messenger.info(f"Creating Laravel project at: '{self.project_root}'...")

        try:
            subprocess.run(
                f'composer global require laravel/installer',
                shell=True,
                check=True
            )
            subprocess.run(
                f'laravel new {self.project_root}',
                shell=True,
                check=True
            )

            Messenger.success("Laravel project created.")

        except subprocess.CalledProcessError:
            Messenger.error("Laravel project creation failed.")
            return

        empty_folder_contents(self.project_views_path)

        restructure_files(self.source_path, self.project_views_path, new_extension=LARAVEL_EXTENSION,
                          skip_dirs=['partials'])

        self._convert()

        self._add_routing_controller_file()

        self._add_routes_web_file()

        copy_assets(self.assets_path, self.project_assets_path, preserve=LARAVEL_RESOURCES_PRESERVE)

        Messenger.completed(f"Project '{self.project_name}' setup", str(self.project_root))

    def _convert(self):

        count = 0

        for file in self.project_views_path.rglob("*"):
            if file.is_file() and file.suffix == ".php":
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()

                original_content = content

                soup = BeautifulSoup(content, 'html.parser')

                # Extract title from title-meta include
                title_meta_match = re.search(
                    r'@@include\(["\']\.\/partials\/title-meta\.html["\']\s*,\s*(array\(.*?\)|{.*?})\)',
                    content,
                    flags=re.DOTALL
                )
                layout_title = ""
                if title_meta_match:
                    meta_data = self._extract_params_from_include(title_meta_match.group())
                    layout_title = meta_data.get("title", "").strip()

                # Build @extends line
                if layout_title:
                    escaped_layout_title = layout_title.replace("'", "\\'")
                    extends_line = f"@extends('layouts.vertical', ['title' => '{escaped_layout_title}'])"
                else:
                    extends_line = "@extends('layouts.vertical')"

                # --- Extract global assets (links and scripts) from the entire document ---
                # These will be pushed into their respective Blade stacks
                link_tags = soup.find_all("link")
                links_html = "\n".join(f"    {str(link)}" for link in link_tags)

                scripts_html = soup.find_all("script")

                # Process scripts for Vite conversion based on src path
                processed_scripts_lines = []
                for script_tag in scripts_html:
                    src_attr = script_tag.get('src')

                    # Check for include remnants (should ideally be gone by this stage)
                    if script_tag.string and "@@include" in script_tag.string:
                        continue  # Skip if it looks like an unconverted include within script

                    if src_attr:
                        # Normalize src_attr: Remove leading '/', './', '../'
                        normalized_src_attr = re.sub(r'^(?:(?:\.\/|\.\.\/)*\/)*', '', src_attr)

                        # Path starts with 'assets/js/' and is not excluded
                        if normalized_src_attr.startswith('assets/js/') and \
                                not normalized_src_attr.startswith('assets/js/vendor/') and \
                                not normalized_src_attr.startswith('assets/js/libs/') and \
                                not normalized_src_attr.startswith('assets/js/plugins/'):

                            # Replace "assets/" with "resources/"
                            transformed_src_attr = normalized_src_attr.replace("assets/", "resources/", 1)
                            processed_scripts_lines.append(f"    @vite(['{transformed_src_attr}'])")

                        # Path starts with 'js/' (but not 'assets/js/') and is not excluded
                        # This covers cases like original src="/js/pages/chart.js"
                        elif normalized_src_attr.startswith('js/') and \
                                not normalized_src_attr.startswith('js/vendor/') and \
                                not normalized_src_attr.startswith('js/libs/') and \
                                not normalized_src_attr.startswith('js/plugins/'):

                            # Prepend "resources/"
                            transformed_src_attr = "resources/" + normalized_src_attr
                            processed_scripts_lines.append(f"    @vite(['{transformed_src_attr}'])")

                        else:
                            # Keep as standard script tag for any other case (vendor, libs, plugins, external, etc.)
                            processed_scripts_lines.append(f"    {str(script_tag)}")
                    else:  # No src attribute (inline script)
                        processed_scripts_lines.append(f"    {str(script_tag)}")

                scripts_html_output = "\n".join(processed_scripts_lines)

                # --- Determine the content for @section('content') based on fallback logic ---
                base_content_for_section = ""
                content_source_info = ""

                content_div = soup.find(attrs={"data-content": True})
                if content_div:
                    base_content_for_section = content_div.decode_contents()
                    content_source_info = "data-content attribute"
                else:
                    body_tag = soup.find("body")
                    if body_tag:
                        base_content_for_section = body_tag.decode_contents()
                        content_source_info = "<body> tag"
                    else:
                        # If neither data-content nor <body> found, use the entire original content
                        # and then remove elements that are typically handled globally (head, links, scripts)
                        base_content_for_section = original_content
                        content_source_info = "entire file (no data-content or <body> found)"

                        # Create a temporary BeautifulSoup object to safely remove tags for this section
                        temp_soup = BeautifulSoup(base_content_for_section, 'html.parser')

                        # Remove head tag (and its children)
                        if temp_soup.head:
                            temp_soup.head.decompose()

                        # Remove all link tags (as they are already extracted for @push('head_links'))
                        for link_tag in temp_soup.find_all("link"):
                            link_tag.decompose()

                        # Remove all script tags (as they are already extracted for @push('body_scripts'))
                        for script_tag in temp_soup.find_all("script"):
                            script_tag.decompose()

                        # Convert the modified soup back to a string
                        if temp_soup.body:  # If there's still a body after head removal
                            base_content_for_section = temp_soup.body.decode_contents()
                        else:  # If it was a fragment or body was not parsed
                            # Get string of current soup content and remove typical top-level document tags
                            base_content_for_section = str(temp_soup)
                            base_content_for_section = re.sub(r'<!DOCTYPE html[^>]*>', '', base_content_for_section,
                                                              flags=re.IGNORECASE)
                            base_content_for_section = re.sub(r'<html[^>]*>|</html>', '', base_content_for_section,
                                                              flags=re.IGNORECASE)
                            base_content_for_section = re.sub(r'<body[^>]*>|</body>', '', base_content_for_section,
                                                              flags=re.IGNORECASE)
                            base_content_for_section = base_content_for_section.strip()  # Final trim

                Messenger.info(f"For '{file.name}': Content for @section('content') taken from {content_source_info}.")

                # `inner_html` is now the content for the section, stripped of global assets
                inner_html = base_content_for_section

                # --- Process page-title within the determined inner_html ---
                page_title_match = re.search(
                    r'@@include\(\s*["\']\.\/partials\/page-title(?:\.html)?["\']\s*,\s*(array\(.*?\)|{.*?})\s*\)',
                    inner_html,
                    flags=re.DOTALL
                )
                if page_title_match:
                    page_data = self._extract_params_from_include(page_title_match.group())
                    blade_include = self._format_page_title_blade_include(page_data)
                    inner_html = re.sub(
                        r'@@include\(\s*["\']\.\/partials\/page-title(?:\.html)?["\']\s*,\s*(array\(.*?\)|{.*?})\s*\)',
                        blade_include,
                        inner_html,
                        flags=re.DOTALL,
                        count=1  # Replace only the first match
                    )
                else:
                    # If no page-title include found, remove any lingering plain @@include for page-title
                    inner_html = re.sub(
                        r'@@include\(\s*["\']\.\/partials\/page-title(?:\.html)?["\'].*?\)',
                        '',
                        inner_html,
                        flags=re.DOTALL
                    )

                content_section = inner_html.strip()  # This is the final content for the Blade section

                blade_output = f"""{extends_line}

    @section('styles')
    {links_html}
    @endsection

    @section('content')
    {content_section}
    @endsection

    @section('scripts')
    {scripts_html_output}
    @endsection
    """

                blade_output = clean_relative_asset_paths(blade_output)

                # Write the converted content to the file
                with open(file, "w", encoding="utf-8") as f:
                    f.write(blade_output.strip() + "\n")

                Messenger.success(f"Converted: {file.relative_to(self.project_views_path)}")
                count += 1

        Messenger.success(f"\n{count} files converted successfully.")

    def _extract_params_from_include(self, include_string):
        """
        Extracts parameters from an @@include string, handling both JSON and PHP array syntax.
        Returns a dictionary of parameters.
        """
        # Try to match JSON first
        json_match = re.search(r'\{([\s\S]*)\}', include_string)
        if json_match:
            try:
                # Attempt to parse as JSON
                json_str = json_match.group(0)
                # Replace single quotes with double quotes for JSON compatibility
                json_str = json_str.replace("'", '"')
                # Handle unquoted keys if any (e.g., {key: "value"})
                json_str = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', json_str)
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass  # Fall through to PHP array parsing if JSON fails

        # Try to match PHP array syntax
        array_match = re.search(r'array\(([\s\S]*)\)', include_string)
        if array_match:
            params_str = array_match.group(1)
            params_dict = {}
            # Regex to find key => value pairs. Handles string keys/values and numeric/boolean values.
            # This is a simplified parser and might not cover all edge cases of PHP array syntax.
            # It assumes string keys are quoted, and string values are quoted.
            param_pattern = re.compile(r"""
                (?:['"](?P<key>[^'"]+)['"]\s*=>\s*)? # Optional quoted key followed by =>
                (?:
                    ['"](?P<sval>(?:\\.|[^'"])*)['"] # String value (handles escaped quotes)
                    |
                    (?P<nval>-?\d+(?:\.\d+)?) # Numeric value
                    |
                    (?P<bool>true|false) # Boolean value
                )
                \s*(?:,\s*|$) # Comma or end of string
            """, re.VERBOSE | re.DOTALL)

            for match in param_pattern.finditer(params_str):
                key = match.group('key')
                if key is None:
                    # If key is not explicitly given, it's an indexed array in PHP.
                    # For our purpose (passing named parameters to Blade), we expect keys.
                    # If you have indexed arrays in your @@include, this part needs more logic.
                    continue

                value = None
                if match.group('sval') is not None:
                    value = match.group('sval').replace('\\"', '"').replace("\\'", "'")  # Unescape quotes
                    # Handle unicode escapes like \uXXXX
                    value = value.encode('latin1').decode('unicode_escape')
                elif match.group('nval') is not None:
                    value = float(match.group('nval')) if '.' in match.group('nval') else int(match.group('nval'))
                elif match.group('bool') is not None:
                    value = True if match.group('bool') == 'true' else False

                params_dict[key] = value
            return params_dict

        Messenger.warning(f"Could not extract parameters from include string: {include_string}")
        return {}

    def _format_blade_include_params(self, data_dict):
        """
        Formats a Python dictionary into a Blade-compatible array string for @include parameters.
        e.g., {"title": "Hello", "icon": "star"} -> "'title' => 'Hello', 'icon' => 'star'"
        """
        params_list = []
        for key, value in data_dict.items():
            # Escape single quotes and backslashes in string values for PHP/Blade
            if isinstance(value, str):
                escaped_value = value.replace('\\', '\\\\').replace("'", "\\'")
                params_list.append(f"'{key}' => '{escaped_value}'")
            elif isinstance(value, bool):
                params_list.append(f"'{key}' => {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                params_list.append(f"'{key}' => {value}")
            else:
                # Fallback for other types, try to represent as string
                params_list.append(f"'{key}' => '{str(value).replace('\'', '\\\'')}'")
        return ", ".join(params_list)

    def _format_page_title_blade_include(self,data_dict):
        """
        Generates the full Blade @include directive for page-title with all parameters.
        """
        formatted_params = self._format_blade_include_params(data_dict)
        return f"@include('layouts.shared.page-title', [{formatted_params}])"

    def _add_routing_controller_file(self):

        self.project_controllers_path.mkdir(parents=True, exist_ok=True)

        controller_content = r"""<?php

    namespace App\Http\Controllers;

    use Illuminate\Support\Facades\Auth;
    use Illuminate\Http\Request;

    class RoutingController extends Controller
    {

        public function index(Request $request)
        {
            return view('index');
        }

        public function root(Request $request, $first)
        {
            return view($first);
        }

        public function secondLevel(Request $request, $first, $second)
        {
            return view($first . '.' . $second);
        }

        public function thirdLevel(Request $request, $first, $second, $third)
        {
            return view($first . '.' . $second . '.' . $third);
        }
    }
    """
        try:
            with open(self.project_controllers_path, "w", encoding="utf-8") as f:
                f.write(controller_content.strip() + "\n")
            Messenger.success(
                f"Created controller file: {self.project_controllers_path.relative_to(self.project_root)}")
        except Exception as e:
            Messenger.error(f"Error writing to {self.project_controllers_path}: {e}")

    def _add_routes_web_file(self):

        self.project_routes_path.parent.mkdir(parents=True, exist_ok=True)

        routes_content = r"""<?php

    use Illuminate\Support\Facades\Route;
    use App\Http\Controllers\RoutingController;

    Route::group(['prefix' => '/'], function () {
        Route::get('', [RoutingController::class, 'index'])->name('root');
        Route::get('{first}/{second}/{third}', [RoutingController::class, 'thirdLevel'])->name('third');
        Route::get('{first}/{second}', [RoutingController::class, 'secondLevel'])->name('second');
        Route::get('{any}', [RoutingController::class, 'root'])->name('any');
    });
    """
        try:
            with open(self.project_routes_path, "w", encoding="utf-8") as f:
                f.write(routes_content.strip() + "\n")
            Messenger.updated(f"routing file: {self.project_routes_path.relative_to(self.project_root)}")
        except Exception as e:
            Messenger.error(f"Error writing to {self.project_routes_path}: {e}")
