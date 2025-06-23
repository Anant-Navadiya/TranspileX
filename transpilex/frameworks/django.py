import re
import json
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from cookiecutter.main import cookiecutter
import sys

from transpilex.helpers import copy_assets, change_extension_and_copy


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
        return f'{attr}="{{% static \'{normalized}\' %}}"'

    return re.sub(r'\b(href|src)\s*=\s*["\'](?:\./|\.\./)*assets/([^"\']+)["\']', replacer, html)


def replace_html_links_with_django_urls(html_content):
    """
    Replaces direct .html links in anchor tags (<a>) with Django {% url %} tags.
    Handles 'index.html' specifically to map to the root URL '/'.
    Example: <a href="dashboard-clinic.html"> -> <a href="{% url 'pages:dynamic_pages' template_name='dashboard-clinic' %}">
    Example: <a href="index.html"> -> <a href="/">
    """
    # Regex to find href attributes in <a> tags that end with .html
    # Group 1: everything before the actual path (e.g., <a ... href=" )
    # Group 2: the .html file path (e.g., dashboard-clinic.html, ../folder/page.html)
    # Group 3: everything after the path until the closing '>' of the <a> tag
    pattern = r'(<a\s+[^>]*?href\s*=\s*["\'])([^"\'#]+\.html)(["\'][^>]*?>)'

    def replacer(match):
        pre_path = match.group(1)  # e.g., <a ... href="
        file_path_full = match.group(2)  # e.g., dashboard-clinic.html or ../folder/page.html
        post_path = match.group(3)  # e.g., " ... >

        # Extract the base filename without extension
        # Path() handles relative paths and extracts the clean stem (filename without extension)
        template_name = Path(file_path_full).stem

        # Special case for 'index.html'
        if template_name == 'index':
            django_url_tag = "/"
        else:
            # Construct the new Django URL tag for other pages
            django_url_tag = f"{{% url 'pages:dynamic_pages' template_name='{template_name}' %}}"

        # Reconstruct the anchor tag with the new href
        return f"{pre_path}{django_url_tag}{post_path}"

    return re.sub(pattern, replacer, html_content)


def convert_to_django_templates(folder):
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

        # Step 3: Replace .html links with Django {% url %} tags
        content = replace_html_links_with_django_urls(content)

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

        with open(file, "w", encoding="utf-8") as f:
            f.write(final_output + "\n")

        print(f"✅ Processed: {file.relative_to(base_path)}")
        count += 1

    print(f"\n✨ {count} templates (layouts + partials) converted successfully.")


def create_django_project(project_name, source_folder, assets_folder):
    project_root = Path("django") / project_name
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create the Django project
    print(f"📦 Creating Django project '{project_root}'...")
    try:
        cookiecutter(
            'https://github.com/cookiecutter/cookiecutter-django',
            output_dir=str(project_root.parent),
            no_input=True,
            extra_context={'project_name': project_name, 'frontend_pipeline': 'Gulp', 'username_type': 'email',
                           'open_source_license': 'Not open source'},
        )

        print("✅ Django project created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create Django project. Make sure Composer and PHP are set up correctly.")
        return

    # --- Start: Modify production.txt ---
    prod_requirements_file = project_root / "requirements" / "production.txt"
    unwanted_package = "psycopg[c]"
    if prod_requirements_file.exists():
        print(f"\n📝 Modifying '{prod_requirements_file}' to remove '{unwanted_package}'...")
        try:
            lines = prod_requirements_file.read_text().splitlines()
            filtered_lines = [line for line in lines if not line.strip().startswith(unwanted_package)]
            prod_requirements_file.write_text("\n".join(filtered_lines))
            print(f"✅ '{unwanted_package}' removed from '{prod_requirements_file}'.")
        except Exception as e:
            print(f"❌ Error modifying '{prod_requirements_file}': {e}")
            return
    else:
        print(f"⚠️ Warning: '{prod_requirements_file}' not found. Skipping modification.")
    # --- End: Modify production.txt ---
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
        local_requirements_file = project_root / "requirements" / "local.txt"
        if local_requirements_file.exists():
            print(f"🚀 Installing dependencies from '{local_requirements_file}' into virtual environment...")
            subprocess.run([str(venv_pip), "install", "-r", str(local_requirements_file)], check=True)
            print("✅ Dependencies from local.txt installed.")
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
    app_name ="pages"
    manage_py_path = project_root / "manage.py"
    app_creation_target_dir = project_root / project_name
    # For cookiecutter-django, settings are often configured to use local.py during development
    # If debug_toolbar is only in local.py and you're running manage.py locally, this is fine.
    settings_file_name = "base.py"
    settings_py_path = project_root / "config" / "settings" / settings_file_name

    if not manage_py_path.exists():
        print(
            f"❌ Error: manage.py not found at {manage_py_path}. This indicates an issue with cookiecutter project creation or its pathing.")
        print(f"Please manually inspect the directory: {project_root}")
        return
    print(f"📂 Creating Django app '{app_name}'...")
    try:
        absolute_manage_py_path = manage_py_path.resolve()
        command = [str(venv_python), str(absolute_manage_py_path), "startapp", app_name]
        print(f"Executing command: {' '.join(command)}")
        print(f"With cwd: {app_creation_target_dir}")
        subprocess.run(
            command,
            cwd=app_creation_target_dir,
            check=True,
            capture_output=True,
            text=True
        )
        print(f"✅ Django app '{app_name}' created successfully.")
        if settings_py_path.exists():
            print(f"✍️ Registering app '{app_name}' in {settings_py_path}...")
            with open(settings_py_path, 'r+') as f:
                content = f.read()
                new_content = re.sub(
                    r"(INSTALLED_APPS = \[.*?)(?:\])",
                    r"\1\n    '{}',\n]".format(app_name),
                    content,
                    flags=re.DOTALL
                )
                f.seek(0)
                f.write(new_content)
                f.truncate()
            print(f"✅ App '{app_name}' registered successfully.")
        else:
            print(
                f"⚠️ Warning: settings.py not found at {settings_py_path}. Please add '{app_name}' to INSTALLED_APPS manually.")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating/registering app '{app_name}': {e.stderr}")
        print(f"Command run: {' '.join(command)}")
        print(f"Return code: {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return
    except Exception as e:
        print(f"❌ An unexpected error occurred while creating/registering app: {e}")
        return

        # --- Start: Add views.py and urls.py to the new 'pages' app ---
    pages_app_dir = app_creation_target_dir / app_name  # This is the actual 'pages' app directory

    views_content = """from django.shortcuts import render

from django.template import TemplateDoesNotExist


def root_page_view(request):
    try:
        return render(request, 'pages/index.html')
    except TemplateDoesNotExist:
        return render(request, 'pages/pages-404.html')


def dynamic_pages_view(request, template_name):
    try:
        return render(request, f'pages/{template_name}.html')
    except TemplateDoesNotExist:
        return render(request, f'pages/pages-404.html')
"""
    urls_content = """from django.urls import path
from pages.views import (root_page_view, dynamic_pages_view)

app_name = "pages"

urlpatterns = [
    path('', root_page_view, name="dashboard"),
    path('<str:template_name>/', dynamic_pages_view, name='dynamic_pages')
]
"""

    views_py_path = pages_app_dir / "views.py"
    urls_py_path = pages_app_dir / "urls.py"

    print(f"📄 Writing content to '{views_py_path}'...")
    try:
        views_py_path.write_text(views_content)
        print(f"✅ '{views_py_path.name}' created.")
    except Exception as e:
        print(f"❌ Error writing to '{views_py_path}': {e}")
        return

    print(f"📄 Writing content to '{urls_py_path}'...")
    try:
        urls_py_path.write_text(urls_content)
        print(f"✅ '{urls_py_path.name}' created.")
    except Exception as e:
        print(f"❌ Error writing to '{urls_py_path}': {e}")
        return

    main_urls_file_path = project_root / "config" / "urls.py"
    # --- Start: Include pages app URLs in main config/urls.py ---
    print(f"\n🔗 Including '{app_name}' app URLs in '{main_urls_file_path}'...")
    if main_urls_file_path.exists():
        try:
            with open(main_urls_file_path, 'r+') as f:
                content = f.read()
                # The line to insert
                url_include_line = f"    path(\"\", include(\"{project_name}.{app_name}.urls\", namespace=\"{app_name}\")),\n"
                # Regex to find the insertion point and avoid inserting if already present
                # Looking for the line with 'Your stuff: custom urls includes go here' or similar
                # And ensuring the exact include line isn't already there.
                if url_include_line.strip() not in content:  # Check if line is already present
                    # This regex matches the "Your stuff: custom urls includes go here" comment
                    # and captures the preceding whitespace to maintain indentation.
                    pattern = r"(\s*# Your stuff: custom urls includes go here)"
                    new_content = re.sub(
                        pattern,
                        r"\1\n" + url_include_line,  # Insert after the matched comment
                        content,
                        count=1  # Only replace the first occurrence
                    )
                    f.seek(0)
                    f.write(new_content)
                    f.truncate()
                    print(f"✅ URLs for '{app_name}' app included successfully.")
                else:
                    print(f"⚠️ URLs for '{app_name}' app already present in '{main_urls_file_path}'. Skipping.")
        except Exception as e:
            print(f"❌ Error including URLs in '{main_urls_file_path}': {e}")
            return
    else:
        print(f"⚠️ Warning: Main URLs file '{main_urls_file_path}' not found. Skipping URL inclusion.")
    # --- End: Include pages app URLs ---





    # Copy the source file and change extensions
    pages_path = project_root / project_name / "templates" / "pages"
    pages_path.mkdir(parents=True, exist_ok=True)

    change_extension_and_copy('html', source_folder, pages_path)

    convert_to_django_templates(pages_path)

    # Copy assets to webroot while preserving required files
    assets_path = project_root / project_name / "static"
    copy_assets(assets_folder, assets_path)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")
