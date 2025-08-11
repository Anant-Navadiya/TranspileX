import re
import json
import shutil
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.config.base import LARAVEL_DESTINATION_FOLDER, LARAVEL_ASSETS_FOLDER, \
    LARAVEL_EXTENSION, LARAVEL_RESOURCES_PRESERVE
from transpilex.helpers import copy_assets
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.messages import Messenger
from transpilex.helpers.restructure_files import restructure_files


class LaravelConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(LARAVEL_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / LARAVEL_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "resources" / "views")
        self.project_routes_path = Path(self.project_root / "routes" / "web.php")
        self.project_controllers_path = Path(self.project_root / "app" / "Http" / "Controllers")
        self.project_route_controller_path = Path(self.project_controllers_path / "RoutingController.php")

        self.create_project()

    def create_project(self):

        Messenger.project_start(self.project_name)

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

            Messenger.success("Laravel project created")

        except subprocess.CalledProcessError:
            Messenger.error("Laravel project creation failed")
            return

        empty_folder_contents(self.project_views_path)

        restructure_files(self.source_path, self.project_views_path, new_extension=LARAVEL_EXTENSION,
                          ignore_list=['partials'])

        self._convert()

        self._add_routing_controller_file()

        self._add_routes_web_file()

        public_only = self._copy_public_assets()

        copy_assets(
            self.assets_path,
            self.project_assets_path,
            preserve=LARAVEL_RESOURCES_PRESERVE,
            exclude=public_only
        )

        Messenger.project_end(self.project_name, str(self.project_root))

    def _convert(self):

        # Generic include finder (handles mixed quotes and JSON/PHP-array params)
        include_re = re.compile(
            r"""@@include\(
                \s*["'](?P<path>[^"']+)["']      # include path
                (?:\s*,\s*(?P<params>\{[\s\S]*?\}|array\([\s\S]*?\)))?   # optional params
                \s*\)""",
            re.VERBOSE
        )

        count = 0

        for file in self.project_views_path.rglob("*"):
            if file.is_file() and file.suffix == ".php":
                with open(file, "r", encoding="utf-8") as f:
                    content = f.read()

                original_content = content
                soup = BeautifulSoup(content, 'html.parser')

                # Title (@extends)
                layout_title = ""
                for m in include_re.finditer(content):
                    inc_path = m.group('path')
                    base = Path(inc_path).name.lower()
                    if base in {"title-meta.html", "app-meta-title.html"}:
                        meta_data = self._extract_params_from_include(m.group(0))
                        layout_title = (meta_data.get("title")
                                        or meta_data.get("pageTitle")
                                        or "").strip()
                        if layout_title:
                            break

                if layout_title:
                    escaped_layout_title = layout_title.replace("'", "\\'")
                    extends_line = f"@extends('layouts.vertical', ['title' => '{escaped_layout_title}'])"
                else:
                    extends_line = "@extends('layouts.vertical')"

                # ---------- Global assets ----------
                link_tags = soup.find_all("link")
                links_html = "\n".join(f"    {str(link)}" for link in link_tags)

                scripts_html = soup.find_all("script")
                processed_scripts_lines = []
                for script_tag in scripts_html:
                    src_attr = script_tag.get('src')

                    if script_tag.string and "@@include" in script_tag.string:
                        continue

                    if src_attr:
                        normalized_src_attr = re.sub(r'^(?:(?:\.\/|\.\.\/)*\/)*', '', src_attr)

                        if normalized_src_attr.startswith('assets/js/') and \
                                not normalized_src_attr.startswith('assets/js/vendor/') and \
                                not normalized_src_attr.startswith('assets/js/libs/') and \
                                not normalized_src_attr.startswith('assets/js/plugins/'):

                            transformed_src_attr = normalized_src_attr.replace("assets/", "resources/", 1)
                            processed_scripts_lines.append(f"    @vite(['{transformed_src_attr}'])")

                        elif normalized_src_attr.startswith('js/') or normalized_src_attr.startswith('scripts/') and \
                                not normalized_src_attr.startswith('js/vendor/') and \
                                not normalized_src_attr.startswith('js/libs/') and \
                                not normalized_src_attr.startswith('js/plugins/'):

                            transformed_src_attr = "resources/" + normalized_src_attr
                            processed_scripts_lines.append(f"    @vite(['{transformed_src_attr}'])")

                        else:
                            processed_scripts_lines.append(f"    {str(script_tag)}")
                    else:
                        processed_scripts_lines.append(f"    {str(script_tag)}")

                scripts_html_output = "\n".join(processed_scripts_lines)

                # ---------- Choose content ----------
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
                        base_content_for_section = original_content
                        content_source_info = "entire file (no data-content or <body> found)"

                        temp_soup = BeautifulSoup(base_content_for_section, 'html.parser')
                        if temp_soup.head:
                            temp_soup.head.decompose()
                        for link_tag in temp_soup.find_all("link"):
                            link_tag.decompose()
                        for script_tag in temp_soup.find_all("script"):
                            script_tag.decompose()

                        if temp_soup.body:
                            base_content_for_section = temp_soup.body.decode_contents()
                        else:
                            base_content_for_section = str(temp_soup)
                            base_content_for_section = re.sub(r'<!DOCTYPE html[^>]*>', '', base_content_for_section,
                                                              flags=re.IGNORECASE)
                            base_content_for_section = re.sub(r'<html[^>]*>|</html>', '', base_content_for_section,
                                                              flags=re.IGNORECASE)
                            base_content_for_section = re.sub(r'<body[^>]*>|</body>', '', base_content_for_section,
                                                              flags=re.IGNORECASE)
                            base_content_for_section = base_content_for_section.strip()

                inner_html = base_content_for_section

                # ---------- Replace page-title/app-pagetitle include with Blade ----------
                def _replace_page_title_include(match: re.Match) -> str:
                    inc_path = match.group('path')
                    base = Path(inc_path).name.lower()
                    if base not in {"page-title.html", "app-pagetitle.html"}:
                        return match.group(0)
                    params = self._extract_params_from_include(match.group(0))
                    return self._format_page_title_blade_include(params)

                inner_html = re.sub(
                    include_re,
                    _replace_page_title_include,
                    inner_html
                )
                inner_html = re.sub(
                    r"""@@include\(\s*["']\.\/partials\/(?:page-title|app-pagetitle)(?:\.html)?["'][^)]*\)""",
                    '',
                    inner_html,
                    flags=re.IGNORECASE
                )

                content_section = inner_html.strip()

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

                with open(file, "w", encoding="utf-8") as f:
                    f.write(blade_output.strip() + "\n")

                Messenger.converted(
                    f"{str(file.relative_to(self.project_views_path))} (content is taken from {content_source_info})")
                count += 1

        Messenger.info(f"{count} files converted in {self.project_views_path}")

    def _extract_params_from_include(self, include_string):
        """
        Extracts parameters from an @@include string, handling both JSON and PHP array syntax.
        Supports mixed single/double quotes and trailing commas.
        """
        m_json = re.search(r'\{[\s\S]*\}', include_string)
        if m_json:
            s = m_json.group(0)

            # Strip JS-style comments (// ... and /* ... */)
            s = re.sub(r'//.*?$', '', s, flags=re.MULTILINE)
            s = re.sub(r'/\*[\s\S]*?\*/', '', s)

            # Convert single-quoted strings to double quotes (values and keys) where safe
            s = re.sub(r'(?<!\\)\'([^\'"]*?)\'', r'"\1"', s)
            s = re.sub(r'([{,]\s*)([A-Za-z_][\w-]*)(\s*:)', r'\1"\2"\3', s)

            # Remove trailing commas
            while True:
                new_s = re.sub(r',(\s*[}\]])', r'\1', s)
                if new_s == s:
                    break
                s = new_s

            try:
                return json.loads(s)
            except json.JSONDecodeError:
                pass  # fallthrough to PHP array

        m_arr = re.search(r'array\s*\(([\s\S]*)\)', include_string)
        if m_arr:
            body = m_arr.group(1)
            params_dict = {}

            param_pattern = re.compile(r"""
                (?:['"](?P<key>[^'"]+)['"]\s*=>\s*)?
                (?:
                    ['"](?P<sval>(?:\\.|[^'"])*)['"]
                    |
                    (?P<nval>-?\d+(?:\.\d+)?)
                    |
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

        Messenger.warning(f"Could not extract parameters from include string: {include_string}")
        return {}

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
            Messenger.created(
                f"controller file {self.project_route_controller_path.relative_to(self.project_root)}")
        except Exception as e:
            Messenger.error(f"Error writing to {self.project_route_controller_path}: {e}")

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
            Messenger.updated(f"routing file {self.project_routes_path.relative_to(self.project_root)}")
        except Exception as e:
            Messenger.error(f"Error writing to {self.project_routes_path}: {e}")

    # ---------- copy selected asset folders to public ----------
    def _copy_public_assets(self) -> set[str]:
        public_root = self.project_root / "public"
        public_root.mkdir(parents=True, exist_ok=True)

        candidates = ["images", "img", "media", "data", "json"]
        copied = set()

        for name in candidates:
            src = self.assets_path / name
            if src.exists() and src.is_dir():
                dest = public_root / name
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(src, dest)
                copied.add(name)
                Messenger.copied(f"{src} → {dest}")

        return copied
