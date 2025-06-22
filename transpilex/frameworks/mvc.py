import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.helpers import copy_assets
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.restructure_files import apply_casing
from transpilex.helpers.update_package_json import update_package_json


def extract_page_title(content: str):
    """Extract title/subtitle from page-title.html or fallback to title-meta.html"""
    page_title_pattern = r'@@include\(\s*["\']\./partials/page-title.html["\']\s*,\s*({.*?})\s*\)'
    title_meta_pattern = r'@@include\(\s*["\']\./partials/title-meta.html["\']\s*,\s*({.*?})\s*\)'

    view_title = None
    view_subtitle = None

    match = re.search(page_title_pattern, content)
    if match:
        try:
            json_data = json.loads(match.group(1).replace("'", '"'))
            view_title = json_data.get("title")
            view_subtitle = json_data.get("subtitle")
        except Exception:
            pass
        content = re.sub(page_title_pattern, '@await Html.PartialAsync("~/Pages/Shared/Partials/_PageTitle.cshtml")',
                         content)
        return view_title, view_subtitle, content

    match = re.search(title_meta_pattern, content)
    if match:
        try:
            json_data = json.loads(match.group(1).replace("'", '"'))
            view_title = json_data.get("title")
        except Exception:
            pass

    return view_title, None, content


def create_controller_file(path, controller_name, actions, app_name):
    """Creates a controller file with basic action methods."""
    using_statements = "using Microsoft.AspNetCore.Mvc;"

    controller_class = f"""
namespace {app_name}.Controllers
{{
    public class {controller_name}Controller : Controller
    {{
{"".join([f"""        public IActionResult {action}()
        {{
            return View();
        }}\n\n""" for action in actions])}    }}
}}
""".strip()

    with open(path, "w", encoding="utf-8") as f:
        f.write(using_statements + "\n\n" + controller_class)


def create_controllers(app_name, views_folder, destination_folder, ignore_list=None):
    """
    Generates controller files based on folders and .cshtml files in the views folder.
    Deletes existing Controllers folder and recreates it.

    :param app_name: The namespace (usually your ASP.NET app name)
    :param views_folder: Path to the Views folder
    :param destination_folder: Where to create the Controllers folder
    :param ignore_list: List of folder or file names to ignore
    """
    ignore_list = ignore_list or []

    controllers_path = os.path.join(destination_folder, "Controllers")

    # 🔥 Remove Controllers folder if it exists
    if os.path.isdir(controllers_path):
        print(f"🧹 Removing existing Controllers folder: {controllers_path}")
        shutil.rmtree(controllers_path)

    os.makedirs(controllers_path, exist_ok=True)

    for folder_name in os.listdir(views_folder):
        if folder_name in ignore_list:
            continue

        folder_path = os.path.join(views_folder, folder_name)
        if not os.path.isdir(folder_path):
            continue

        actions = []
        for file in os.listdir(folder_path):
            if file in ignore_list:
                continue
            if file.endswith(".cshtml") and not file.endswith(".cshtml.cs") and not file.startswith("_"):
                action_name = os.path.splitext(file)[0]
                actions.append(action_name)

        if actions:
            controller_file_path = os.path.join(controllers_path, f"{folder_name}Controller.cs")
            create_controller_file(controller_file_path, folder_name, actions, app_name)
            print(f"✅ Created: {controller_file_path}")

    print("✨ Controller generation completed.")


def restructure_files(src_folder, dist_folder, new_extension="cshtml", skip_dirs=None, casing="pascal"):
    src_path = Path(src_folder)
    dist_path = Path(dist_folder)
    copied_count = 0

    if skip_dirs is None:
        skip_dirs = []

    for file in src_path.rglob("*.html"):
        if not file.is_file() or any(skip in file.parts for skip in skip_dirs):
            continue

        with open(file, "r", encoding="utf-8") as f:
            raw_html = f.read()

        view_title, view_subtitle, cleaned_html = extract_page_title(raw_html)

        # Parse the entire HTML document
        soup = BeautifulSoup(cleaned_html, "html.parser")
        is_partial = "partials" in file.parts

        # --- Extract scripts and links from the entire document first ---
        script_tags = soup.find_all('script')
        link_tags = soup.find_all('link', rel='stylesheet')

        scripts_content = "\n    ".join([str(tag) for tag in script_tags])
        styles_content = "\n    ".join([str(tag) for tag in link_tags])

        # Remove scripts and links from their original positions
        for tag in script_tags + link_tags:
            tag.decompose()  # This removes the tag from the soup object

        # --- Now, determine the main content block for the CSHTML body ---
        if is_partial:
            # For partials, the entire cleaned HTML (after removing scripts/links) is the content
            main_content = soup.decode_contents().strip()
        else:
            content_block = soup.find(attrs={"data-content": True})
            if content_block:
                main_content = content_block.decode_contents().strip()
            elif soup.body:
                # If no data-content and it's not a partial, take the body content
                main_content = soup.body.decode_contents().strip()
            else:
                # Fallback to entire content if no body or data-content
                main_content = soup.decode_contents().strip()

        base_name = file.stem

        if '-' in base_name:
            name_parts = [part.replace("_", "-") for part in base_name.split('-')]
            final_file_name = name_parts[-1]
            folder_name_parts = name_parts[:-1]
        else:
            folder_name_parts = [base_name.replace("_", "-")]
            final_file_name = "index"

        processed_folder_parts = [apply_casing(p, casing) for p in folder_name_parts]
        processed_file_name = apply_casing(final_file_name, casing)

        final_ext = new_extension if new_extension.startswith(".") else f".{new_extension}"
        target_dir = dist_path / Path(*processed_folder_parts)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{processed_file_name}{final_ext}"

        route_path = "/" + base_name.lower().replace("_", "-")

        if not view_title:
            view_title = processed_file_name

        viewbag_lines = [f'ViewBag.Title = "{view_title}";']
        if view_subtitle:
            viewbag_lines.append(f'ViewBag.SubTitle = "{view_subtitle}";')
        viewbag_code = "\n    ".join(viewbag_lines)

        cshtml_content = f"""@{{
    {viewbag_code}
}}

@section styles
{{
    {styles_content}
}}

{main_content}

@section scripts
{{
    {scripts_content}
}}"""

        # Clean asset paths
        cshtml_content = clean_relative_asset_paths(cshtml_content)

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(cshtml_content.strip() + "\n")

        print(f"✅ Created: {target_file.relative_to(dist_path)}")
        copied_count += 1

    print(f"\n✨ {copied_count} .cshtml files generated from HTML sources.")


def create_mvc_project(project_name, source_folder, assets_folder):
    project_root = Path("mvc") / project_name.title()
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create the MVC project using Composer
    print(f"📦 Creating MVC project '{project_root}'...")
    try:
        subprocess.run(
            f'dotnet new mvc -n {project_name.title()}',
            cwd=project_root.parent,
            shell=True,
            check=True
        )
        print("✅ MVC project created successfully.")

        subprocess.run(
            f'dotnet new sln -n {project_name.title()}',
            cwd=project_root.parent,
            shell=True,
            check=True
        )

        sln_file = f"{project_name.title()}.sln"

        subprocess.run(
            f'dotnet sln {sln_file} add {Path(project_name.title()) / project_name.title()}.csproj',
            cwd=project_root.parent,
            shell=True,
            check=True
        )

        print("✅ .sln file created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create MVC project. Make sure Composer and PHP are set up correctly.")
        return

    # Copy source files into templates/Pages/ as .php files
    pages_path = project_root / "Views"
    pages_path.mkdir(parents=True, exist_ok=True)

    restructure_files(source_folder, pages_path, new_extension='cshtml', skip_dirs=['partials'], casing="pascal")

    print(f"\n🔧 Converting includes in '{pages_path}'...")

    create_controllers(project_name.title(), pages_path, project_root,['Shared'])

    # Copy assets to webroot while preserving required files
    assets_path = project_root / "wwwroot"
    copy_assets(assets_folder, assets_path)

    # Create gulpfile.js
    create_gulpfile_js(project_root, './wwwroot')

    # Update dependencies
    update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
