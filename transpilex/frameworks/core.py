import json
import subprocess
import os
from pathlib import Path

from bs4 import BeautifulSoup

from transpilex.helpers import copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.restructure_files import apply_casing
from transpilex.helpers.update_package_json import update_package_json


def extract_page_title(content: str):
    """Find @@include for page-title.html and extract subtitle + title from JSON."""
    import re
    pattern = r'@@include\(\s*["\']\.\/partials\/page-title\.html["\']\s*,\s*({.*?})\s*\)'
    match = re.search(pattern, content)
    if match:
        try:
            json_data = json.loads(match.group(1))
            subtitle = json_data.get("subtitle", "Pages")
            title = json_data.get("title", "Untitled")
            # Remove the include line from HTML
            content = re.sub(pattern, '', content)
            return title.strip(), subtitle.strip(), content
        except Exception:
            pass
    return None, None, content


def set_content(namespace, model_name):
    """Generates default content for .cshtml.cs files."""
    return f"""using Microsoft.AspNetCore.Mvc.RazorPages;

namespace {namespace}
{{
    public class {model_name} : PageModel
    {{
        public void OnGet() {{ }}
    }}
}}
"""

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

        # Extract ViewBag.Title and SubTitle from @@include if found
        view_title, view_subtitle, cleaned_html = extract_page_title(raw_html)

        soup = BeautifulSoup(cleaned_html, "html.parser")
        is_partial = "partials" in file.parts

        # Extract content based on file type
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

        if '-' in base_name:
            name_parts = [part.replace("_", "-") for part in base_name.split('-')]
            final_file_name = name_parts[-1]
            folder_name_parts = name_parts[:-1]
        else:
            folder_name_parts = [base_name.replace("_", "-")]
            final_file_name = "index"

        # Apply casing
        processed_folder_parts = [apply_casing(p, casing) for p in folder_name_parts]
        processed_file_name = apply_casing(final_file_name, casing)

        # Final destination
        final_ext = new_extension if new_extension.startswith(".") else f".{new_extension}"
        target_dir = dist_path / Path(*processed_folder_parts)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{processed_file_name}{final_ext}"

        # Route path with _ replaced by -
        route_path = "/" + base_name.lower().replace("_", "-")

        # Fallbacks for title/subtitle if not extracted
        if not view_title:
            view_title = processed_file_name
        if not view_subtitle:
            view_subtitle = processed_folder_parts[-1] if processed_folder_parts else "Pages"

        # Final Razor content
        cshtml_content = f"""@page "{route_path}"
@model TEMP_NAMESPACE.{processed_file_name}Model

@{{
    ViewBag.Title = "{view_title}";
    ViewBag.SubTitle = "{view_subtitle}";
}}

@await Html.PartialAsync("~/Pages/Shared/Partials/_PageTitle.cshtml")

{main_content}

@section scripts
{{
    <!-- Scripts can be injected here -->
}}"""

        # Write file
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

        # Also patch namespace in the .cshtml view
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
    project_root = Path("core") / project_name
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create the Core project using Composer
    print(f"📦 Creating Core project '{project_root}'...")
    try:
        subprocess.run(
            f'dotnet new web -n {project_name}',
            cwd=project_root.parent,
            shell=True,
            check=True
        )
        print("✅ Core project created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create Core project. Make sure Composer and PHP are set up correctly.")
        return

    # Copy source files into templates/Pages/ as .php files
    pages_path = project_root / "Pages"
    pages_path.mkdir(parents=True, exist_ok=True)

    restructure_files(source_folder, pages_path, new_extension='cshtml', skip_dirs=['partials'], casing="pascal")

    add_additional_extension_files(project_name, pages_path)

    # Convert @@include to Core syntax in all .php files inside templates/Pages/
    print(f"\n🔧 Converting includes in '{pages_path}'...")
    # convert_to_core(pages_path)

    # Copy assets to webroot while preserving required files
    assets_path = project_root / "wwwroot"
    copy_assets(assets_folder, assets_path)

    # Create gulpfile.js
    create_gulpfile_js(project_root, './wwwroot')

    # Update dependencies
    update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
