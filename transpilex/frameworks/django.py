import re
import json
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from cookiecutter.main import cookiecutter
import sys

from transpilex.helpers import copy_assets, change_extension_and_copy
from transpilex.helpers.empty_folder_contents import empty_folder_contents


def extract_json_from_include(json_str):
    try:
        json_text = json_str.replace("'", '"')
        return json.loads(json_text)
    except Exception:
        return None  # None means keep original

def format_django_include_dynamic(context_dict):
    parts = []
    for key, value in context_dict.items():
        if isinstance(value, str):
            val = f"'{value}'"
        elif isinstance(value, (int, float, bool)):
            val = str(value).lower() if isinstance(value, bool) else str(value)
        elif value is None:
            val = "None"
        else:
            continue
        parts.append(f"{key}={val}")
    return f"{{% include 'partials/page-title.html' with {' '.join(parts)} %}}"

def find_balanced_json(text, start_index):
    """Extracts a balanced JSON block starting from the given index."""
    brace_count = 0
    end_index = start_index
    while end_index < len(text):
        char = text[end_index]
        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                return text[start_index:end_index + 1], end_index + 1
        end_index += 1
    return None, start_index

def replace_page_title_include(content):
    pattern = r'@@include\(\s*[\'"](?:\.\/)?partials/page-title\.html[\'"]\s*,\s*'

    result = []
    index = 0

    for match in re.finditer(pattern, content):
        result.append(content[index:match.start()])
        json_start = match.end()
        json_str, next_index = find_balanced_json(content, json_start)

        if json_str:
            try:
                data = json.loads(json_str.replace("'", '"'))
                replacement = format_django_include_dynamic(data)
                result.append(replacement)
            except Exception as e:
                print(f"⚠️ Failed to parse JSON in page-title include: {e}")
                result.append(content[match.start():next_index])
        else:
            print("⚠️ Could not find balanced JSON block.")
            result.append(content[match.start():json_start])

        index = next_index

    result.append(content[index:])
    return ''.join(result)


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
    base_path = Path(folder)
    count = 0

    for file in base_path.rglob("*.html"):
        print(f"Processing: {file.relative_to(base_path)}")
        with open(file, "r", encoding="utf-8") as f:
            content = f.read()

        # Replace page-title includes
        content = replace_page_title_include(content)

        # Extract layout title from title-meta
        title_meta_match = re.search(r'@@include\(["\']\./partials/title-meta\.html["\']\s*,\s*({.*?})\)', content)
        layout_title = "Untitled"
        if title_meta_match:
            meta_data = extract_json_from_include(title_meta_match.group(1))
            layout_title = meta_data.get("title", "Untitled").strip()
            content = re.sub(r'@@include\(["\']\./partials/title-meta\.html["\']\s*,\s*({.*?})\)', '', content)

        # Clean static and links
        content = clean_static_paths(content)
        content = replace_html_links_with_django_urls(content)

        # Parse the soup
        soup = BeautifulSoup(content, "html.parser")

        # Flexible layout detection: body or data-content
        is_layout = bool(soup.find("body") or soup.find(attrs={"data-content": True}))

        if is_layout:
            head_tag = soup.find("head")
            links_html = "\n".join(str(tag) for tag in head_tag.find_all("link")) if head_tag else ""

            # Collect scripts (full soup)
            scripts_html = "\n".join(str(tag) for tag in soup.find_all("script"))

            # Extract main content: data-content > body > None
            content_section = None
            content_div = soup.find(attrs={"data-content": True})
            if content_div:
                div_clone = BeautifulSoup(str(content_div), "html.parser")
                for script_tag in div_clone.find_all("script"):
                    script_tag.decompose()
                content_section = div_clone.decode_contents().strip()
            elif soup.body:
                body_clone = BeautifulSoup(str(soup.body), "html.parser")
                for script_tag in body_clone.find_all("script"):
                    script_tag.decompose()
                content_section = body_clone.body.decode_contents().strip()

            if content_section:
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
{{% endblock scripts %}}"""
                final_output = re.sub(r"@@include\([^)]+\)", "", django_template.strip())
            else:
                print("⚠️ No data-content or body found. Keeping original content.")
                final_output = re.sub(r"@@include\([^)]+\)", "", content.strip())
        else:
            # Not a layout
            final_output = re.sub(r"@@include\([^)]+\)", "", content.strip())

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
            # This path is the entry point to the virtual environment
            venv_python = venv_dir / "bin" / "python3"
            venv_pip = venv_dir / "bin" / "pip3"

        if not venv_python.exists():
            print(f"❌ Error: Virtual environment Python executable not found at {venv_python}")
            return

        # Install Django and other dependencies into the virtual environment
        print("📦 Installing dependencies from local.txt...")
        local_requirements_path = project_root / "requirements" / "local.txt"
        try:
            subprocess.run(
                [str(venv_pip), "install", "-r", str(local_requirements_path)],
                check=True,
                capture_output=True,
                text=True
            )
            print("✅ Dependencies from local.txt installed.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Error installing dependencies: {e}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
            return

        app_name = "pages"
        manage_py_path = project_root / "manage.py"  # This is Path('django/tonely/manage.py')
        app_creation_target_dir = project_root / project_name  # This is Path('django/tonely/tonely')

        print(f"📂 Creating Django app '{app_name}'...")
        try:
            # **** THE CRUCIAL CHANGE: Convert only the venv_python and manage_py_path
            # **** to absolute strings without resolving symlinks all the way to the system python.
            # **** Path.absolute() is often better than Path.resolve() for this scenario.

            # Get the absolute path to the venv's python executable
            # This typically does not follow symlinks *outside* the virtual environment's immediate setup.
            # It just makes the current Path object absolute relative to CWD.
            absolute_venv_python_cmd = str(venv_python.absolute())

            # Get the absolute path to manage.py
            absolute_manage_py_path_cmd = str(manage_py_path.absolute())

            command = [absolute_venv_python_cmd, absolute_manage_py_path_cmd, "startapp", app_name]
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

        except subprocess.CalledProcessError as e:
            print(f"❌ Error creating/registering app '{app_name}': {e}")
            print(f"Command run: {' '.join(e.cmd)}")
            print(f"Return code: {e.returncode}")
            print(f"Stdout: {e.stdout}")
            print(f"Stderr: {e.stderr}")
        except Exception as e:
            print(f"❌ An unexpected error occurred while creating/registering app: {e}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error creating virtual environment: {e}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")

    empty_folder_contents(project_root / project_name / 'templates' / 'pages')

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
