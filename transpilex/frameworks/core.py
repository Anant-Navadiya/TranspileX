import json
import re
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.helpers import copy_assets
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.replace_html_links import replace_html_links
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
        content = re.sub(page_title_pattern, '@await Html.PartialAsync("~/Pages/Shared/Partials/_PageTitle.cshtml")', content)
        return view_title, view_subtitle, content

    match = re.search(title_meta_pattern, content)
    if match:
        try:
            json_data = json.loads(match.group(1).replace("'", '"'))
            view_title = json_data.get("title")
        except Exception:
            pass

    return view_title, None, content

def set_content(namespace, model_name):
    return f"""using Microsoft.AspNetCore.Mvc.RazorPages;

namespace {namespace}
{{
    public class {model_name} : PageModel
    {{
        public void OnGet() {{ }}
    }}
}}"""


def restructure_files(src_folder, dist_folder, new_extension="cshtml", skip_dirs=None, casing="pascal"):
    src_path = Path(src_folder)
    dist_path = Path(dist_folder)
    copied_count = 0

    if skip_dirs is None:
        skip_dirs = []

    for file in src_path.rglob("*.html"):
        if not file.is_file() or any(skip in file.parts for skip in skip_dirs):
            continue

        relative_path = file.relative_to(src_path)

        with open(file, "r", encoding="utf-8") as f:
            raw_html = f.read()

        view_title, view_subtitle, cleaned_html = extract_page_title(raw_html)

        soup = BeautifulSoup(cleaned_html, "html.parser")
        is_partial = "partials" in file.parts

        script_tags = soup.find_all('script')
        link_tags = soup.find_all('link', rel='stylesheet')

        scripts_content = "\n    ".join([str(tag) for tag in script_tags])
        styles_content = "\n    ".join([str(tag) for tag in link_tags])

        for tag in script_tags + link_tags:
            tag.decompose()

        if is_partial:
            main_content = soup.decode_contents().strip()
        else:
            content_block = soup.find(attrs={"data-content": True})
            if content_block:
                main_content = content_block.decode_contents().strip()
            elif soup.body:
                main_content = soup.body.decode_contents().strip()
            else:
                main_content = soup.decode_contents().strip()

        base_name = file.stem

        # ⬇️ Derive folder and file from file name (like "dashboard-home" → ["dashboard", "home"])
        if '-' in base_name:
            name_parts = [part.replace("_", "-") for part in base_name.split('-')]
            final_file_name = name_parts[-1]
            file_based_folders = name_parts[:-1]
        else:
            file_based_folders = [base_name.replace("_", "-")]
            final_file_name = "index"

        # ⬇️ Combine folders from both relative folder structure and file name
        relative_folder_parts = list(relative_path.parent.parts)  # original folders in src
        combined_folder_parts = relative_folder_parts + file_based_folders
        processed_folder_parts = [apply_casing(p, casing) for p in combined_folder_parts]
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

        cshtml_content = f"""@page \"{route_path}\"
@model TEMP_NAMESPACE.{processed_file_name}Model

@{{
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

        cshtml_content = clean_relative_asset_paths(cshtml_content)
        cshtml_content = replace_html_links(cshtml_content, '')

        with open(target_file, "w", encoding="utf-8") as f:
            f.write(cshtml_content.strip() + "\n")

        print(f"✅ Created: {target_file.relative_to(dist_path)}")
        copied_count += 1

    print(f"\n✨ {copied_count} .cshtml files generated from HTML sources.")

def add_additional_extension_files(project_name, dist_folder, new_ext="cshtml", additional_ext="cshtml.cs"):
    dist_path = Path(dist_folder)
    generated_count = 0

    pascal_app_name = apply_casing(project_name, "pascal")

    for file in dist_path.rglob(f"*.{new_ext}"):
        file_name = file.stem
        folder_parts = file.relative_to(dist_path).parent.parts
        folder_path = file.parent

        model_name = f"{file_name}Model"
        namespace = f"{pascal_app_name}.Pages" + (
            '.' + '.'.join([apply_casing(p, 'pascal') for p in folder_parts]) if folder_parts else "")

        new_file_path = folder_path / f"{file_name}.{additional_ext}"
        content = set_content(namespace, model_name)

        with open(file, "r+", encoding="utf-8") as f:
            view = f.read()
            view = view.replace("TEMP_NAMESPACE", namespace)
            f.seek(0)
            f.write(view)
            f.truncate()

        try:
            with open(new_file_path, "w", encoding="utf-8") as f:
                f.write(content.strip() + "\n")
            print(f"📝 Created: {new_file_path.relative_to(dist_path)}")
            generated_count += 1
        except IOError as e:
            print(f"❌ Error writing {new_file_path}: {e}")

    print(f"\n✅ {generated_count} .{additional_ext} files generated.")

def create_core_project(project_name, source_folder, assets_folder):
    project_root = Path("core") / project_name.title()
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create the Core project using Composer
    print(f"📦 Creating Core project '{project_root}'...")
    try:
        subprocess.run(
            f'dotnet new web -n {project_name.title()}',
            cwd=project_root.parent,
            shell=True,
            check=True
        )
        print("✅ Core project created successfully.")

        subprocess.run(
            f'dotnet new sln -n {project_name.title()}',
            cwd=project_root.parent,
            shell=True,
            check=True
        )

        sln_file =  f"{project_name.title()}.sln"

        subprocess.run(
            f'dotnet sln {sln_file} add {Path(project_name.title()) / project_name.title()}.csproj',
            cwd=project_root.parent,
            shell=True,
            check=True
        )

        print("✅ .sln file created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create Core project. Make sure Dotnet SDK is installed correctly.")
        return

    # Copy source files into templates/Pages/ as .php files
    pages_path = project_root / "Pages"
    pages_path.mkdir(parents=True, exist_ok=True)

    restructure_files(source_folder, pages_path, new_extension='cshtml', skip_dirs=['partials'], casing="pascal")

    add_additional_extension_files(project_name, pages_path)

    print(f"\n🔧 Converting includes in '{pages_path}'...")

    # Copy assets to webroot while preserving required files
    assets_path = project_root / "wwwroot"
    copy_assets(assets_folder, assets_path)

    # Create gulpfile.js
    create_gulpfile_js(project_root, './wwwroot')

    # Update dependencies
    update_package_json(source_folder, project_root, project_name)


    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
