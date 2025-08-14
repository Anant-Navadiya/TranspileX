import re
import json
import shutil
import html
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

from transpilex.config.base import LARAVEL_DESTINATION_FOLDER, LARAVEL_ASSETS_FOLDER, \
    LARAVEL_EXTENSION, LARAVEL_RESOURCES_PRESERVE, LARAVEL_AUTH_FOLDER, LARAVEL_INSTALLER_COMMAND, \
    LARAVEL_PROJECT_CREATION_COMMAND, LARAVEL_PROJECT_CREATION_COMMAND_AUTH
from transpilex.helpers import copy_assets, change_extension_and_copy
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.copy_assets import copy_assets_in_public
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.git import remove_git_folder
from transpilex.helpers.logs import Log
from transpilex.helpers.package_json import sync_package_json
from transpilex.helpers.restructure_files import restructure_files
from transpilex.helpers.validations import folder_exists


class LaravelConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, auth: bool = False):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(LARAVEL_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / LARAVEL_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "resources" / "views")
        self.project_partials_path = Path(self.project_views_path / "partials")

        self.project_routes_path = Path(self.project_root / "routes" / "web.php")
        self.project_controllers_path = Path(self.project_root / "app" / "Http" / "Controllers")
        self.project_route_controller_path = Path(self.project_controllers_path / "RoutingController.php")
        self.project_vite_path = Path(self.project_root / "vite.config.js")

        self.ROUTE_STRICT = True  # only change routes when exact match exists
        self.href_route_index = self._build_route_index()

        self.vite_inputs = set()

        self.auth_required = auth

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        if self.auth_required:
            try:
                self.project_root.mkdir(parents=True, exist_ok=True)

                subprocess.run(LARAVEL_PROJECT_CREATION_COMMAND_AUTH, cwd=self.project_root, check=True,
                               capture_output=True, text=True)

                Log.success("Laravel project created successfully")

                remove_git_folder(self.project_root)

            except subprocess.CalledProcessError:
                Log.error("Laravel project creation failed")
                return

        else:
            try:
                subprocess.run(LARAVEL_INSTALLER_COMMAND, shell=True, check=True)
                subprocess.run(f'{LARAVEL_PROJECT_CREATION_COMMAND} {self.project_root}', shell=True, check=True)
                Log.success("Laravel project created successfully")

            except subprocess.CalledProcessError:
                Log.error("Laravel project creation failed")
                return

        if not self.auth_required:
            empty_folder_contents(self.project_views_path)

        restructure_files(self.source_path, self.project_views_path, new_extension=LARAVEL_EXTENSION,
                          ignore_list=['partials', LARAVEL_AUTH_FOLDER])

        self._copy_partials()

        self._convert()

        self._replace_partial_variables()

        if not self.auth_required:
            self._add_routing_controller_file()
            self._add_routes_web_file()

        public_only = copy_assets_in_public(self.assets_path, self.project_assets_path)

        copy_assets(
            self.assets_path,
            self.project_assets_path,
            preserve=LARAVEL_RESOURCES_PRESERVE,
            exclude=public_only
        )

        sync_package_json(self.source_path, self.project_root)

        self._update_vite_config()

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):

        include_re = re.compile(
            r"""@@include\(
                      \s*["'](?P<path>[^"']+)["']
                      (?:\s*,\s*(?P<params>\{[\s\S]*?\}|array\([\s\S]*?\)))?
                      \s*\)""",
            re.VERBOSE
        )

        count = 0

        for file in self.project_views_path.rglob("*.php"):

            rel_parts = file.relative_to(self.project_views_path).parts[:-1]
            if any(p in {LARAVEL_AUTH_FOLDER} for p in rel_parts):
                continue

            is_partial = 'partials' in file.relative_to(self.project_views_path).parts

            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')

            if is_partial:
                # For partials, process scripts directly on the soup object.
                for script_tag in soup.find_all("script"):
                    src_attr = script_tag.get('src')
                    if src_attr:
                        normalized_src_attr = re.sub(r'^(?:(?:\.\/|\.\.\/)*\/)*', '', src_attr)
                        transformed_src_attr = ""
                        if normalized_src_attr.startswith('assets/js/') and not normalized_src_attr.startswith(
                                ('assets/js/vendor/', 'assets/js/libs/', 'assets/js/plugins/')):
                            transformed_src_attr = normalized_src_attr.replace("assets/", "resources/", 1)
                        elif normalized_src_attr.startswith(
                                ('js/', 'scripts/')) and not normalized_src_attr.startswith(
                            ('js/vendor/', 'js/libs/', 'js/plugins/')):
                            transformed_src_attr = "resources/" + normalized_src_attr
                        if transformed_src_attr:
                            vite_directive = f"@vite(['{transformed_src_attr}'])"
                            script_tag.replace_with(NavigableString(vite_directive))
                            self.vite_inputs.add(transformed_src_attr)

                # Get the modified HTML and then process the includes
                modified_html = str(soup)
                final_content = self._replace_all_includes_with_blade(modified_html, include_re)

                final_output = clean_relative_asset_paths(final_content)

                final_output = self._rewrite_routes(final_output)

                with open(file, "w", encoding="utf-8") as f:
                    f.write(final_output)
                Log.converted(f"{str(file.relative_to(self.project_views_path))} (processed as partial)")
                count += 1

            else:
                # Find title from the ORIGINAL content before modifications
                layout_title = ""
                for m in include_re.finditer(content):
                    if Path(m.group('path')).name.lower() in {"title-meta.html", "app-meta-title.html"}:
                        meta_data = self._extract_params_from_include(m.group(0))
                        layout_title = (meta_data.get("title") or meta_data.get("pageTitle") or "").strip()
                        if layout_title: break

                escaped_layout_title = layout_title.replace("'", "\\'") if layout_title else ''
                extends_line = f"@extends('layouts.vertical', ['title' => '{escaped_layout_title}'])" if layout_title else "@extends('layouts.vertical')"

                # Collect and remove link tags for the 'styles' section
                links_html_list = []
                for link_tag in soup.find_all("link"):
                    links_html_list.append(f"    {str(link_tag)}")
                    link_tag.decompose()
                links_html = "\n".join(links_html_list)

                # Collect, process, and remove script tags for the 'scripts' section
                scripts_output_list = []
                for script_tag in soup.find_all("script"):
                    src_attr = script_tag.get('src')
                    output_line = str(script_tag)

                    if src_attr:
                        normalized_src_attr = re.sub(r'^(?:(?:\.\/|\.\.\/)*\/)*', '', src_attr)
                        transformed_src_attr = ""
                        if normalized_src_attr.startswith('assets/js/') and not normalized_src_attr.startswith(
                                ('assets/js/vendor/', 'assets/js/libs/', 'assets/js/plugins/')):
                            transformed_src_attr = normalized_src_attr.replace("assets/", "resources/", 1)
                        elif normalized_src_attr.startswith(
                                ('js/', 'scripts/')) and not normalized_src_attr.startswith(
                            ('js/vendor/', 'js/libs/', 'js/plugins/')):
                            transformed_src_attr = "resources/" + normalized_src_attr

                        if transformed_src_attr:
                            output_line = f"@vite(['{transformed_src_attr}'])"
                            self.vite_inputs.add(transformed_src_attr)

                    scripts_output_list.append(f"    {output_line}")
                    script_tag.decompose()
                scripts_html_output = "\n".join(scripts_output_list)

                # Extract the main content from the now-cleaned soup
                content_div = soup.find(attrs={"data-content": True})
                if content_div:
                    base_content_for_section = content_div.decode_contents()
                elif soup.body:
                    base_content_for_section = soup.body.decode_contents()
                else:
                    if soup.head: soup.head.decompose()
                    base_content_for_section = str(soup)

                # Process all @@includes within the extracted content
                content_section = self._replace_all_includes_with_blade(base_content_for_section,
                                                                        include_re).strip()

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
                final_output = clean_relative_asset_paths(blade_output)

                final_output = self._rewrite_routes(final_output)

                with open(file, "w", encoding="utf-8") as f:
                    f.write(final_output.strip() + "\n")

                Log.converted(f"{str(file.relative_to(self.project_views_path))} (processed as full page)")
                count += 1

        Log.info(f"{count} files converted in {self.project_views_path}")

    def _replace_all_includes_with_blade(self, content: str, include_re: re.Pattern):
        """
        A generic replacer that converts any @@include into a Blade @include.
        """

        def _replacer(match: re.Match):
            inc_path_str = match.group('path')

            # Exclude title includes from this generic replacement, they are handled separately
            if Path(inc_path_str).name.lower() in {"title-meta.html", "app-meta-title.html"}:
                return ''  # Remove title includes, as they are used for the @extends line

            params = {}
            # Only try to extract params if the regex actually found them.
            if match.group('params'):
                params = self._extract_params_from_include(match.group(0))

            blade_path = (
                Path(inc_path_str)
                .with_suffix('')
                .as_posix()
                .lstrip('./')
                .replace('/', '.')
            )

            if params:
                formatted_params = self._format_blade_include_params(params)
                return f"@include('{blade_path}', [{formatted_params}])"
            else:
                return f"@include('{blade_path}')"

        return include_re.sub(_replacer, content)

    def _extract_params_from_include(self, include_string: str):
        """
        Robustly extracts and cleans parameters from an @@include string.
        It handles malformed JSON with comments, newlines, single quotes,
        unquoted keys, and trailing commas.
        """
        # First, try to find a JSON-like object (between {})
        param_match = re.search(r'(\{[\s\S]*\})', include_string)
        if param_match:
            s = param_match.group(1)

            # Decode HTML entities (&amp; -> &)
            s = html.unescape(s)

            # Remove JS-style comments (// and /* */)
            s = re.sub(r'//.*?$', '', s, flags=re.MULTILINE)
            s = re.sub(r'/\*[\s\S]*?\*/', '', s)

            # Normalize newlines and excess whitespace inside string values.
            # This is crucial for multi-line strings.
            def _normalize_str_content(match):
                # Get the content inside the quotes (group 1)
                content = match.group(1)
                # Replace newlines, tabs, etc., with a space
                content = re.sub(r'[\n\r\t]', ' ', content)
                # Collapse multiple spaces into one
                content = re.sub(r'\s{2,}', ' ', content).strip()
                # Return the cleaned string within double quotes
                return f'"{content}"'

            # This regex finds content within single or double quotes, handling escaped quotes
            s = re.sub(r'"((?:\\.|[^"\\])*)"', _normalize_str_content, s)
            s = re.sub(r"'((?:\\.|[^'\\])*)'", _normalize_str_content, s)

            # Add double quotes around any unquoted keys (e.g., { key: "value" })
            # Handles keys at the start of the object or after a comma.
            s = re.sub(r'([\{\s,])\s*([a-zA-Z_][\w-]*)\s*:', r'\1"\2":', s)

            # Remove trailing commas (e.g., "value", })
            s = re.sub(r',\s*([\}\]])', r'\1', s)

            # Try to parse the now-clean JSON string
            try:
                # Convert any remaining single-quoted values to double-quoted
                s = re.sub(r":\s*'([^']*)'", r': "\1"', s)
                return json.loads(s)
            except json.JSONDecodeError as e:
                Log.warning(f"Could not parse JSON for: {include_string}. Error: {e}\nCleaned string was: {s}")
                return {}

        # Fallback to PHP array parsing if no JSON object was found
        return self._extract_php_array_params(include_string)

    def _extract_php_array_params(self, include_string: str):
        """
        Handles extraction from PHP array syntax. (Your original PHP logic)
        """
        m_arr = re.search(r'array\s*\(([\s\S]*)\)', include_string)
        if not m_arr:
            return {}

        body = m_arr.group(1)
        params_dict = {}
        param_pattern = re.compile(r"""
            (?:['"](?P<key>[^'"]+)['"]\s*=>\s*)?
            (?:
                ['"](?P<sval>(?:\\.|[^'"])*)['"] |
                (?P<nval>-?\d+(?:\.\d+)?) |
                (?P<bool>true|false)
            )
            \s*(?:,\s*|$)
        """, re.VERBOSE | re.DOTALL)

        for match in param_pattern.finditer(body):
            key = match.group('key')
            if not key:
                continue
            if match.group('sval') is not None:
                value = match.group('sval').replace('\\"', '"').replace("\\'", "'")
                value = value.encode('latin1').decode('unicode_escape')
            elif match.group('nval') is not None:
                value = float(match.group('nval')) if '.' in match.group('nval') else int(match.group('nval'))
            elif match.group('bool') is not None:
                value = True if match.group('bool') == 'true' else False
            else:
                value = ''
            params_dict[key] = value
        return params_dict

    def _format_blade_include_params(self, data_dict):
        """
        Formats a Python dictionary into a Blade-compatible array string for @include parameters.
        """
        params_list = []
        for key, value in data_dict.items():
            if isinstance(value, str):
                escaped_value = value.replace('\\', '\\\\').replace("'", "\\'")
                params_list.append(f"'{key}' => '{escaped_value}'")
            elif isinstance(value, bool):
                params_list.append(f"'{key}' => {'true' if value else 'false'}")
            elif isinstance(value, (int, float)):
                params_list.append(f"'{key}' => {value}")
            else:
                params_list.append(f"'{key}' => '{str(value).replace('\'', '\\\'')}'")
        return ", ".join(params_list)

    def _format_page_title_blade_include(self, data_dict):
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
            with open(self.project_route_controller_path, "w", encoding="utf-8") as f:
                f.write(controller_content.strip() + "\n")
            Log.created(
                f"controller file {self.project_route_controller_path.relative_to(self.project_root)}")
        except Exception as e:
            Log.error(f"Error writing to {self.project_route_controller_path}: {e}")

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
            Log.updated(f"routing file {self.project_routes_path.relative_to(self.project_root)}")
        except Exception as e:
            Log.error(f"Error writing to {self.project_routes_path}: {e}")

    def _copy_partials(self):
        self.project_partials_path.mkdir(parents=True, exist_ok=True)
        partials_source = self.source_path / "partials"

        if partials_source.exists() and partials_source.is_dir():
            change_extension_and_copy(LARAVEL_EXTENSION, partials_source, self.project_partials_path)

    def _replace_partial_variables(self):
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_partials_path.rglob(f"*{LARAVEL_EXTENSION}"):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            new_content = pattern.sub(r'{{ $\1 }}', content)
            if new_content != content:
                file.write_text(new_content, encoding="utf-8")
                Log.updated(str(file))
                count += 1

        if count:
            Log.info(f"{count} files updated in {self.project_partials_path}")

    def _build_route_index(self):
        """
        Map href (with '-' between levels) to a Blade route string derived from
        SOURCE filenames where:
          - '-' splits levels
          - '_' is an intra-level hyphen (not a split)
        Example:
          ai-ton_ai.html -> href key 'ai-ton-ai.html' -> route('second',['ai','ton-ai'])
        """
        index = {}
        for f in self.source_path.rglob("*.html"):
            stem = f.stem  # e.g. "ai-ton_ai", "tables-datatables-export_data"
            levels_raw = stem.split('-')  # '-' defines levels
            levels = [part.replace('_', '-') for part in levels_raw]  # '_' -> '-' inside a level

            if len(levels) == 1:
                route = 'any'
                params = f"'{levels[0]}'"
            elif len(levels) == 2:
                route = 'second'
                params = f"['{levels[0]}', '{levels[1]}']"
            else:
                route = 'third'
                tail = '-'.join(levels[2:])  # merge deeper levels into one slug
                params = f"['{levels[0]}', '{levels[1]}', '{tail}']"

            route_str = f"{{{{ route('{route}', {params}) }}}}"
            # hrefs in markup still use '-' separators and never use '_'
            href_key = "-".join(levels) + ".html"
            index[href_key] = route_str

        return index

    def _route_from_href(self, href_file: str):
        # Prefer source-derived map
        if href_file in self.href_route_index:
            return self.href_route_index[href_file]

        # Fallback: derive from href itself
        base = Path(href_file).stem
        parts = [p.replace('_', '-') for p in base.split('-')]  # normalize just in case
        if len(parts) == 1:
            route, params = 'any', f"'{parts[0]}'"
        elif len(parts) == 2:
            route, params = 'second', f"['{parts[0]}', '{parts[1]}']"
        else:
            route, params = 'third', f"['{parts[0]}', '{parts[1]}', '{'-'.join(parts[2:])}']"
        return f"{{{{ route('{route}', {params}) }}}}"

    def _rewrite_routes(self, html: str):
        pattern = re.compile(r'''href\s*=\s*(['"])(?!http|#|javascript:)([^'"]+?\.html)\1''', re.IGNORECASE)

        def repl(m):
            quote_in = m.group(1)
            file = m.group(2)

            if self.ROUTE_STRICT and file not in self.href_route_index:
                # leave as-is so the user sees it and can change route manually
                # (also log it for convenience)
                Log.warning(f"No exact match for href '{file}'. Left unchanged")
                return m.group(0)

            route = self.href_route_index.get(file)
            if not route:
                # fallback (if strict off): derive from href tokens
                route = self._route_from_href(file)

            # always emit double quotes around href
            return f'href="{route}"'

        return pattern.sub(repl, html)

    def _update_vite_config(self):
        """
        Update (or create) vite.config.js to include collected Vite inputs.
        This version is more robust and less destructive than a simple overwrite.
        """
        # Prepare the new 'input' array string from the current inputs.
        # Sorting ensures a consistent order, which is good for version control.
        inputs_str = ",\n            ".join(f"'{p}'" for p in sorted(self.vite_inputs))
        new_input_block = f"input: [\n            {inputs_str}\n        ]"

        # If the config file exists, attempt to modify it.
        if self.project_vite_path.exists():
            content = self.project_vite_path.read_text(encoding="utf-8")

            # Regex to find an existing `input: [...]` array.
            # re.DOTALL allows '.' to match newlines, handling multi-line arrays.
            input_array_regex = re.compile(r"input\s*:\s*\[[\s\S]*?\]", re.DOTALL)

            # Try to substitute the old input array with the new one.
            new_content, num_replacements = input_array_regex.subn(new_input_block, content, count=1)

            if num_replacements > 0:
                self.project_vite_path.write_text(new_content, encoding="utf-8")
                Log.info(f"Updated vite.config.js with {len(self.vite_inputs)} inputs")
                return

            # If no 'input' array was found, try to inject one into the laravel plugin config.
            laravel_plugin_regex = re.compile(r"(laravel\s*\(\s*\{)", re.DOTALL)
            # Add the input block right after `laravel({`
            injection_block = f"\\1\n        {new_input_block},"
            new_content, num_injections = laravel_plugin_regex.subn(injection_block, content, count=1)

            if num_injections > 0:
                self.project_vite_path.write_text(new_content, encoding="utf-8")
                Log.info(f"Added input array to vite.config.js ({len(self.vite_inputs)} inputs)")
                return

        # Create (or overwrite) the file with a minimal, valid config.
        # This runs if the file doesn't exist, or if it exists but couldn't be modified
        # (e.g., no `laravel({})` block).
        minimal_config = f"""import {{ defineConfig }} from 'vite';
import laravel from 'laravel-vite-plugin';

export default defineConfig({{
    plugins: [
        laravel({{
            {new_input_block},
            refresh: true,
        }}),
    ],
}});
"""
        self.project_vite_path.write_text(minimal_config.strip(), encoding="utf-8")

        Log.info(f"vite.config.js is ready at: {self.project_vite_path}")

