import json
import re
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.helpers import copy_assets
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.add_gulpfile import add_gulpfile
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.restructure_files import apply_casing
from transpilex.helpers.update_package_json import update_package_json


def to_pascal_case(s: str) -> str:
    # First split on _ - and spaces
    parts = re.split(r"[_\-\s]+", s)

    # For each part, split camelCase into separate words
    def split_camel_case(word):
        return re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])', word)

    words = []
    for part in parts:
        words.extend(split_camel_case(part))

    # Capitalize all parts and join
    return "".join(word.capitalize() for word in words if word)


def extract_include_variables(content: str, partial_name="page-title.html"):
    """
    Extract all variables from an @@include for the given partial_name (supports ./partials, ../partials, partials).

    Returns:
        tuple(dict, str): (dictionary of PascalCase keys and values, content with include replaced by Razor partial)
    """
    pattern = (
        r'@@include\(\s*["\'](?:\.{1,2}/)?partials/' + re.escape(partial_name) + r'["\']\s*,\s*({.*?})\s*\)'
    )

    match = re.search(pattern, content, flags=re.DOTALL)
    if match:
        json_str = match.group(1)
        try:
            json_fixed = json_str.replace("'", '"')
            data_raw = json.loads(json_fixed)
        except json.JSONDecodeError:
            data_raw = {}

        data_pascal = {to_pascal_case(k): v for k, v in data_raw.items()}

        replacement = '@await Html.PartialAsync("~/Pages/Shared/Partials/_PageTitle.cshtml")'
        updated_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

        return data_pascal, updated_content

    return {}, content


def generate_viewbag_code(data: dict):
    if not data:
        return ""

    lines = []
    for key, val in data.items():
        val_str = str(val).replace('"', '\\"')
        lines.append(f'ViewBag.{key} = "{val_str}";')

    return "@{\n    " + "\n    ".join(lines) + "\n}"


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
        relative_file_path_str = str(file.relative_to(src_path)).replace("\\", "/")
        if not file.is_file() or any(skip in relative_file_path_str for skip in skip_dirs):
            continue

        relative_path = file.relative_to(src_path)

        with open(file, "r", encoding="utf-8") as f:
            raw_html = f.read()

        # Use the new generic extractor here for "page-title.html" partial
        viewbag_data, cleaned_html = extract_include_variables(raw_html, "page-title.html")

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

        # Derive folder and file from file name (like "dashboard-home" → ["dashboard", "home"])
        if '-' in base_name:
            name_parts = [part.replace("_", "-") for part in base_name.split('-')]
            final_file_name = name_parts[-1]
            file_based_folders = name_parts[:-1]
        else:
            file_based_folders = [base_name.replace("_", "-")]
            final_file_name = "index"

        # Combine folders from relative folder structure and file name parts
        relative_folder_parts = list(relative_path.parent.parts)
        combined_folder_parts = relative_folder_parts + file_based_folders
        processed_folder_parts = [apply_casing(p, casing) for p in combined_folder_parts]
        processed_file_name = apply_casing(final_file_name, casing)

        final_ext = new_extension if new_extension.startswith(".") else f".{new_extension}"
        target_dir = dist_path / Path(*processed_folder_parts)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{processed_file_name}{final_ext}"

        route_path = "/" + base_name.lower().replace("_", "-")

        # Generate ViewBag code from extracted data
        if not viewbag_data.get("Title"):
            # Fallback title to file name if missing
            viewbag_data["Title"] = processed_file_name

        viewbag_code = generate_viewbag_code(viewbag_data)

        cshtml_content = f"""@page \"{route_path}\"
@model TEMP_NAMESPACE.{processed_file_name}Model

{viewbag_code}

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


def add_additional_extension_files(project_name, dist_folder, new_ext="cshtml", additional_ext="cshtml.cs",
                                   skip_paths=None):
    dist_path = Path(dist_folder)
    generated_count = 0

    pascal_app_name = apply_casing(project_name, "pascal")

    if skip_paths is None:
        skip_paths = []

    for file in dist_path.rglob(f"*.{new_ext}"):
        relative_file_path_str = str(file.relative_to(dist_path)).replace("\\", "/")
        if any(skip in relative_file_path_str for skip in skip_paths):
            continue

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

    print(f"📦 Creating Core project '{project_root}'...")
    try:
        subprocess.run(
            f'dotnet new razor -n {project_name.title()}',
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

        sln_file = f"{project_name.title()}.sln"

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

    pages_path = project_root / "Pages"
    pages_path.mkdir(parents=True, exist_ok=True)

    empty_folder_contents(pages_path, skip=['_ViewStart.cshtml', '_ViewImports.cshtml'])

    restructure_files(source_folder, pages_path, new_extension='cshtml', skip_dirs=['partials'], casing="pascal")

    add_additional_extension_files(project_name, pages_path, skip_paths=['_ViewStart.cshtml', '_ViewImports.cshtml'])

    print(f"\n🔧 Converting includes in '{pages_path}'...")

    assets_path = project_root / "wwwroot"
    copy_assets(assets_folder, assets_path)

    add_gulpfile(project_root, './wwwroot')

    # update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
