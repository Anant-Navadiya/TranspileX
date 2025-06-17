import re
import json
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from shutil import move, which

from transpilex.helpers import copy_assets
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.restructure_files import restructure_files


def add_routes_web_file(project_root):
    """
    Adds custom routing configuration to routes/web.php, replacing all existing content.
    """
    routes_file_path = project_root / "routes" / "web.php"

    # Ensure the 'routes' directory exists
    routes_file_path.parent.mkdir(parents=True, exist_ok=True)

    routes_content = """<?php

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
        with open(routes_file_path, "w", encoding="utf-8") as f:
            f.write(routes_content.strip() + "\n")
        print(f"✅ Updated routing file: {routes_file_path.relative_to(project_root)}")
    except Exception as e:
        print(f"❌ Error writing to {routes_file_path}: {e}")


def add_routing_controller_file(project_root):
    """
    Creates App/Http/Controllers/RoutingController.php with the specified content.
    """
    controller_dir = project_root / "app" / "Http" / "Controllers"
    controller_file_path = controller_dir / "RoutingController.php"

    # Ensure the controller directory exists
    controller_dir.mkdir(parents=True, exist_ok=True)

    controller_content = """<?php

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
        with open(controller_file_path, "w", encoding="utf-8") as f:
            f.write(controller_content.strip() + "\n")
        print(f"✅ Created controller file: {controller_file_path.relative_to(project_root)}")
    except Exception as e:
        print(f"❌ Error writing to {controller_file_path}: {e}")


def extract_json_from_include(include_str):
    try:
        match = re.search(r'\{.*\}', include_str)
        if match:
            json_text = match.group().replace("'", '"')
            return json.loads(json_text)
    except Exception:
        pass
    return {}


def format_blade_include(page_title, subtitle):
    parts = []
    if page_title:
        parts.append(f"'page_title' => '{page_title}'")
    if subtitle:
        parts.append(f"'sub_title' => '{subtitle}'")
    if parts:
        return f"@include('layouts.shared.page-title', [{', '.join(parts)}])"
    return ""


def convert_to_laravel(dist_folder):
    dist_path = Path(dist_folder)
    count = 0

    for file in dist_path.rglob("*"):
        if file.is_file() and file.suffix == ".php":
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')

            # Extract title from title-meta include
            title_meta_match = re.search(r'@@include\(["\']\.\/partials\/title-meta\.html["\']\s*,\s*({.*?})\)',
                                         content)
            layout_title = ""
            if title_meta_match:
                meta_data = extract_json_from_include(title_meta_match.group())
                layout_title = meta_data.get("title", "").strip()

            # Build @extends line
            if layout_title:
                extends_line = f"@extends('layouts.vertical', ['title' => '{layout_title}'])"
            else:
                extends_line = "@extends('layouts.vertical')"

            # Extract <link> tags from <head>
            link_tags = soup.find_all("link")
            links_html = "\n".join(f"    {str(link)}" for link in link_tags)

            # Extract <script> tags from entire doc
            scripts_html = "\n".join(f"    {str(tag)}" for tag in soup.find_all("script"))

            # Locate content with data-content
            content_div = soup.find(attrs={"data-content": True})
            if not content_div:
                print(f"⚠️ Skipping '{file.name}': no data-content found.")
                continue
            inner_html = content_div.decode_contents()

            # Replace page-title if present
            page_title_match = re.search(r'@@include\(\s*["\']\.\/partials\/page-title\.html["\']\s*,\s*({.*?})\s*\)',
                                         inner_html)
            if page_title_match:
                page_data = extract_json_from_include(page_title_match.group())
                page_title = page_data.get("title", "").strip()
                subtitle = page_data.get("subtitle", "").strip()
                blade_include = format_blade_include(page_title, subtitle)
                inner_html = re.sub(r'@@include\(\s*["\']\.\/partials\/page-title\.html["\']\s*,\s*{.*?}\s*\)',
                                    blade_include, inner_html)
            else:
                # no include to replace; just clean any leftovers
                inner_html = re.sub(r'@@include\(\s*["\']\.\/partials\/page-title\.html["\'].*?\)', '', inner_html)

            # The content_section is now raw HTML/Blade, Pint will format it later
            content_section = inner_html.strip()

            # Final blade structure
            blade_output = f"""{extends_line}

@section('content')
{content_section}
@endsection

{links_html}

{scripts_html}
"""

            # remove assets from links, scripts
            blade_output = clean_relative_asset_paths(blade_output)

            with open(file, "w", encoding="utf-8") as f:
                f.write(blade_output.strip() + "\n")

            print(f"✅ Converted: {file.relative_to(dist_path)}")
            count += 1

    print(f"\n✨ {count} files converted successfully.")


def create_laravel_project(project_name, source_folder, assets_folder):
    project_root = Path("laravel") / project_name
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create the Codeigniter project using Composer
    print(f"📦 Creating Laravel project '{project_root}'...")
    try:
        subprocess.run(
            f'composer global require laravel/installer',
            shell=True,
            check=True
        )
        subprocess.run(
            f'laravel new {project_root}',
            shell=True,
            check=True
        )
        print("✅ Laravel project created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create Laravel project. Make sure Composer and PHP are set up correctly.")
        return

    # Copy the source file and change extensions
    pages_path = project_root / "resources" / "views"
    pages_path.mkdir(parents=True, exist_ok=True)

    restructure_files(source_folder, pages_path, new_extension='blade.php', skip_dirs=['partials'])

    convert_to_laravel(pages_path)

    add_routing_controller_file(project_root)

    add_routes_web_file(project_root)

    # Copy assets to webroot while preserving required files
    assets_path = project_root / "resources"
    copy_assets(assets_folder, assets_path, preserve=["views"])

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
