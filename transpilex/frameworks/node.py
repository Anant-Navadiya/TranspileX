import re
import json
import subprocess
from pathlib import Path

from transpilex.helpers import change_extension_and_copy, copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json


def extract_meta(content):
    # Try to extract from page-title first
    match_page_title = re.search(r"""@@include\(\s*['"]\.\/partials\/page-title\.html['"]\s*,\s*(\{.*?\})\s*\)""",
                                 content)
    if match_page_title:
        try:
            data = json.loads(match_page_title.group(1))
            return {"title": data.get("title"), "subtitle": data.get("subtitle")}
        except json.JSONDecodeError:
            print("⚠️ Invalid JSON in page-title include.")
            return {}

    # Fallback: try from title-meta
    match_title_meta = re.search(r"""@@include\(\s*['"]\.\/partials\/title-meta\.html['"]\s*,\s*(\{.*?\})\s*\)""",
                                 content)
    if match_title_meta:
        try:
            data = json.loads(match_title_meta.group(1))
            return {"title": data.get("title")}
        except json.JSONDecodeError:
            print("⚠️ Invalid JSON in title-meta include.")
            return {}

    return {}


def generate_route(file_name, meta):
    route_path = "/" if file_name == "index" else f"/{file_name}"
    route = f"route.get('{route_path}', (req, res, next) => {{\n"

    render_line = f"    res.render('{file_name}'"
    if "title" in meta:
        render_line += f", {{ title: '{meta['title']}'"
        if "subtitle" in meta:
            render_line += f", subtitle: '{meta['subtitle']}'"
        render_line += " })"
    render_line += ";"

    route += render_line + "\n});\n"
    return route


def generate_express_routes(view_folder, output_file):
    folder = Path(view_folder)
    if not folder.exists():
        print(f"❌ Folder '{view_folder}' not found.")
        return

    routes_dir = output_file / 'routes'
    routes_dir.mkdir(parents=True, exist_ok=True)

    route_file = routes_dir / 'route.js'

    routes = [
        "const express = require('express');",
        "const route = express.Router();\n"
    ]

    skipped = []

    for file in folder.glob("*.ejs"):
        content = file.read_text(encoding="utf-8")
        file_name = file.stem
        meta = extract_meta(content)

        if not meta.get("title") and not meta.get("subtitle"):
            print(f"⚠️ Skipping '{file_name}.ejs': no title found.")
            skipped.append(file_name)
            continue

        route_code = generate_route(file_name, meta)
        routes.append(route_code)

    routes.append("\nmodule.exports = route;")
    route_file.write_text("\n".join(routes), encoding="utf-8")

    print(f"\n✅ Generated routes in '{output_file}'.")
    if skipped:
        print(f"⚠️ Skipped files with no meta: {', '.join(skipped)}")


def convert_to_node(dist_folder):
    """
    Convert all @@include(...) in .html files to <%- include(...) %> (EJS syntax)
    Removes all parameters passed in include (if any).
    """
    folder = Path(dist_folder)
    updated_files = 0

    for file in folder.rglob("*"):
        if file.is_file() and file.suffix in ['.html', '.ejs']:
            original = file.read_text(encoding="utf-8")
            content = original

            # Convert @@include('path', {...}) → <%- include('path') %>
            content = re.sub(
                r"@@include\(['\"](.+?)['\"]\s*,\s*\{.*?\}\s*\)",
                lambda m: f"<%- include('{strip_extension(m.group(1))}') %>",
                content
            )

            # Convert @@include('path') → <%- include('path') %>
            content = re.sub(
                r"@@include\(['\"](.+?)['\"]\)",
                lambda m: f"<%- include('{strip_extension(m.group(1))}') %>",
                content
            )

            # replace .html with .php in anchor
            content = replace_html_links(content, '')

            if content != original:
                file.write_text(content, encoding="utf-8")
                print(f"✅ Converted: {file}")
                updated_files += 1

    print(f"\n🔄 Done. Updated {updated_files} HTML file(s).")


def strip_extension(path):
    """
    Strip .html or .htm extension from a path string
    """
    return re.sub(r'\.html?$', '', path)


def create_node_project(project_name, source_folder, assets_folder):
    """
    1. Create a new Core project using Composer.
    2. Copy all files from the source_folder to the new project's templates/Pages folder.
    3. Convert the includes to Codeigniter-style using convert_to_codeigniter().
    4. Add HomeController.php to the Controllers folder.
    5. Patch routes.
    6. Copy custom assets to public, preserving required files.
    """

    project_root = Path("node") / project_name
    project_views = project_root / "views"

    print(f"📦 Creating Node project at: '{project_root}'...")
    project_root.mkdir(parents=True, exist_ok=True)

    # Copy HTML -> EJS to views
    change_extension_and_copy("ejs", source_folder, project_views)

    generate_express_routes(project_views, project_root)

    # Replace @@include with PHP include() in .php files
    convert_to_node(project_views)

    # Copy assets
    assets_path = project_root / "assets"
    copy_assets(assets_folder, assets_path)

    # Create gulpfile.js
    create_gulpfile_js(project_root, './assets')

    # Update dependencies
    update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
