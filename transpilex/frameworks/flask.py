import re
import json
import subprocess
from pathlib import Path
import os
from bs4 import BeautifulSoup
from cookiecutter.main import cookiecutter
import sys

from transpilex.helpers import change_extension_and_copy, copy_assets
from transpilex.helpers.replace_html_links import replace_html_links


def replace_page_title_include(content):
    # This version matches single or double quotes and captures flexible spacing
    pattern = r'@@include\(\s*[\'"]\.\/partials\/page-title\.html[\'"]\s*,\s*(\{.*?\})\s*\)'

    def replacer(match):
        data = extract_json_from_include(match.group(1))  # match.group(1) gives the JSON directly
        title = data.get("title", "").strip()
        subtitle = data.get("subtitle", "").strip()
        return format_django_include(title=title, subtitle=subtitle)

    return re.sub(pattern, replacer, content)


def extract_json_from_include(json_str):
    try:
        json_text = json_str.replace("'", '"')
        return json.loads(json_text)
    except Exception:
        return {}


def format_django_include(title=None, subtitle=None):
    parts = []
    if title:
        parts.append(f"title='{title}'")
    if subtitle:
        parts.append(f"subtitle='{subtitle}'")
    if parts:
        return f"{{% include 'partials/page-title.html' with {' '.join(parts)} %}}"
    return ""


def clean_static_paths(html):
    def replacer(match):
        attr = match.group(1)
        path = match.group(2)
        normalized = re.sub(r'^(\.*/)*assets/', '', path)
        return f'{attr}="{{{{ config.ASSETS_ROOT }}}}/{normalized}"'

    return re.sub(r'\b(href|src)\s*=\s*["\'](?:\./|\.\./)*assets/([^"\']+)["\']', replacer, html)

def convert_to_flask_templates(folder):
    """
    Converts HTML files in a given folder to Django template format,
    handling @@includes, static file paths, and HTML link replacements.
    """
    base_path = Path(folder)
    count = 0

    for file in base_path.rglob("*.html"):
        print(f"Processing: {file.relative_to(base_path)}")
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        # Step 1: Handle @@include directives
        # First, page-title.html which has JSON data
        content = replace_page_title_include(content)

        # Handle other @@include directives (e.g., for footer) without JSON data
        content = re.sub(r'@@include\(\s*[\'"]\.\/partials\/footer\.html[\'"]\s*\)',
                         "{% include 'partials/footer.html' %}", content)

        # Handle @@include('./partials/title-meta.html', {...}) for layout title
        # This regex needs to capture the JSON part for title extraction.
        # We process it here to get the layout_title, and then remove it from content.
        title_meta_match = re.search(r'@@include\(["\']\.\/partials\/title-meta\.html["\']\s*,\s*({.*?})\)', content)
        layout_title = "Untitled"  # Default title
        if title_meta_match:
            meta_data = extract_json_from_include(title_meta_match.group(1))  # Capture group 1 is the JSON
            layout_title = meta_data.get("title", "Untitled").strip()
            # Remove the @@include for title-meta, as its content is integrated into {% block title %}
            content = re.sub(r'@@include\(["\']\.\/partials\/title-meta\.html["\']\s*,\s*({.*?})\)', '', content)

        # Step 2: Clean all asset paths (e.g., images, scripts, stylesheets)
        content = clean_static_paths(content)


        # Now, determine if it's a layout file or a partial and format accordingly
        soup = BeautifulSoup(content, "html.parser")
        is_layout = bool(soup.find("html") or soup.find(attrs={"data-content": True}))

        if is_layout:
            # Extract assets and content for layout structure
            # Re-parse with BeautifulSoup after all string replacements for accurate tag finding
            soup_for_extraction = BeautifulSoup(content, "html.parser")

            links_html = "\n".join(str(tag) for tag in soup_for_extraction.find_all("link"))
            scripts_html = "\n".join(str(tag) for tag in soup_for_extraction.find_all("script"))

            # Find the main content block
            content_div = soup_for_extraction.find(attrs={"data-content": True})
            if content_div:
                content_section = content_div.decode_contents().strip()
            elif soup_for_extraction.body:
                content_section = soup_for_extraction.body.decode_contents().strip()
            else:
                # Fallback to entire content if no <body> or data-content attributes
                content_section = soup_for_extraction.decode_contents().strip()

            # Build Django layout
            django_template = f"""{{% extends 'vertical.html' %}}

{{% load static i18n %}}

{{% block title %}}{layout_title}{{% endblock title %}}

{{% block styles %}}
{links_html}
{{% endblock styles %}}

{{% block content %}}
{content_section}
{{% endblock content %}}

{{% block scripts %}}
{scripts_html}
{{% endblock scripts %}}
"""
            final_output = django_template.strip()
        else:
            # For partials that are not layouts, just keep the processed content
            final_output = content.strip()

        # replace .html
        final_output = replace_html_links(final_output, '')

        with open(file, "w", encoding="utf-8") as f:
            f.write(final_output + "\n")

        print(f"✅ Processed: {file.relative_to(base_path)}")
        count += 1

    print(f"\n✨ {count} templates (layouts + partials) converted successfully.")


def create_flask_project(project_name, source_folder, assets_folder):
    project_root = Path("flask") / project_name
    project_root.mkdir(parents=True, exist_ok=True)

    # Create the Flask project
    print(f"📦 Creating Flask project '{project_root}'...")
    try:
        subprocess.run(
            ['git', 'clone', 'https://github.com/Anant-Navadiya/flask-boilerplate.git', '.'],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True
        )

        print("✅ Flask project created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create Flask project. Make sure Composer and PHP are set up correctly.")
        return

    # --- Start: Virtual Environment Setup ---
    venv_dir = project_root / "venv"
    print(f"\n🐍 Creating virtual environment at '{venv_dir}'...")
    try:
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        print("✅ Virtual environment created.")
        if sys.platform == "win32":
            venv_python = venv_dir / "Scripts" / "python.exe"
            venv_pip = venv_dir / "Scripts" / "pip.exe"
        else:
            venv_python = venv_dir / "bin" / "python3"
            venv_pip = venv_dir / "bin" / "pip3"
        if not venv_python.exists():
            print(f"❌ Error: Virtual environment Python executable not found at {venv_python}")
            return
        # --- ONLY INSTALL LOCAL.TXT ---
        local_requirements_file = project_root / "requirements.txt"
        if local_requirements_file.exists():
            print(f"🚀 Installing dependencies from '{local_requirements_file}' into virtual environment...")
            subprocess.run([str(venv_pip), "install", "-r", str(local_requirements_file)], check=True)
            print("✅ Dependencies from requirements.txt installed.")
        else:
            print(
                f"⚠️ Warning: '{local_requirements_file}' not found. Skipping dependency installation from local.txt.")
        # --- END ONLY INSTALL LOCAL.TXT ---
    except subprocess.CalledProcessError as e:
        print(f"❌ Error setting up virtual environment or installing dependencies: {e.stderr}")
        return
    except Exception as e:
        print(f"❌ An unexpected error occurred during virtual environment setup: {e}")
        return
    # --- End: Virtual Environment Setup ---


    # Copy the source file and change extensions
    pages_path = project_root / "apps" / "templates" / "pages"
    pages_path.mkdir(parents=True, exist_ok=True)

    change_extension_and_copy('html', source_folder, pages_path)

    convert_to_flask_templates(pages_path)

    # Copy assets to webroot while preserving required files
    assets_path = project_root / "apps" / "static"
    copy_assets(assets_folder, assets_path)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")