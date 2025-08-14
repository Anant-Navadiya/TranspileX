import re
import ast
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
from cookiecutter.main import cookiecutter

from transpilex.config.base import DJANGO_DESTINATION_FOLDER, DJANGO_ASSETS_FOLDER, DJANGO_COOKIECUTTER_REPO, \
    DJANGO_EXTENSION
from transpilex.helpers import copy_assets, change_extension_and_copy
from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.logs import Log
from transpilex.helpers.move_files import move_files
from transpilex.helpers.package_json import sync_package_json
from transpilex.helpers.validations import folder_exists


class DjangoConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True,
                 auth: bool = False, plugins_config: bool = True):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(DJANGO_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp
        self.plugins_config = plugins_config

        self.project_root = Path(self.destination_path / project_name)
        self.project_assets_path = Path(self.project_root / self.project_name / DJANGO_ASSETS_FOLDER)
        self.project_pages_path = Path(self.project_root / self.project_name / "templates" / "pages")
        self.project_partials_path = Path(self.project_root / self.project_name / "templates" / "partials")
        self.project_auth_path = Path(self.project_root / self.project_name / "templates" / "account")

        self.auth_required = auth

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        try:

            cookiecutter(
                DJANGO_COOKIECUTTER_REPO,
                output_dir=str(self.project_root.parent),
                no_input=True,
                extra_context={'project_name': self.project_name,
                               'frontend_pipeline': 'Gulp' if self.include_gulp else 'None',
                               'plugins_config': 'y' if self.plugins_config else 'n', 'username_type': 'email',
                               'open_source_license': 'Not open source', 'auth': 'y' if self.auth_required else 'n'
                               },
            )

            Log.success("Django project created successfully")

        except subprocess.CalledProcessError:
            Log.error("Django project creation failed")
            return

        self.project_pages_path.mkdir(parents=True, exist_ok=True)

        change_extension_and_copy(DJANGO_EXTENSION, self.source_path, self.project_pages_path)

        self._convert()

        partials_source = self.project_pages_path / "partials"

        if partials_source.exists() and partials_source.is_dir():
            self.project_partials_path.mkdir(parents=True, exist_ok=True)
            move_files(partials_source, self.project_partials_path)

        self._replace_partial_variables()

        if not self.auth_required:
            empty_folder_contents(self.project_auth_path)

        copy_assets(self.assets_path, self.project_assets_path)

        sync_package_json(self.source_path, self.project_root, ignore_gulp=not self.include_gulp)

        if self.include_gulp and self.plugins_config:
            add_plugins_file(self.source_path, self.project_root)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):
        """
        Converts HTML files to Django templates using a generic and robust
        approach for all @@include directives.
        """
        count = 0
        for file in self.project_pages_path.rglob("*.html"):
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            # Step 1: Handle the special case for the main page title.
            title_meta_pattern = re.compile(
                r'@@include\(\s*[\'"]\.\/partials\/(title-meta|app-meta-title)\.html[\'"]\s*,\s*(\{.*?\})\s*\)',
                re.DOTALL,
            )
            title_meta_match = title_meta_pattern.search(content)

            layout_title = "Untitled"
            if title_meta_match:
                meta_data_str = title_meta_match.group(2)
                meta_data = self._extract_data_from_include(meta_data_str)
                layout_title = meta_data.get("title", meta_data.get("pageTitle", "Untitled")).strip()
                content = title_meta_pattern.sub("", content, count=1)

            # Step 2: Generically convert ALL other @@include directives.
            generic_include_pattern = re.compile(
                r'@@include\(\s*[\'"](.+?)[\'"]\s*(?:,\s*(\{.*?\})\s*)?\)', re.DOTALL
            )
            content = generic_include_pattern.sub(self._generic_include_replacer, content)

            # Step 3: Clean static paths and internal .html links.
            # This must happen BEFORE parsing with BeautifulSoup to handle all paths correctly.
            content_with_static_paths = self._clean_static_paths(content)
            final_content = self._replace_html_links_with_django_urls(content_with_static_paths)

            # Step 4: Determine if the file is a full layout and wrap it with a base template.
            soup = BeautifulSoup(final_content, "html.parser")
            is_layout = bool(soup.find("body") or soup.find(attrs={"data-content": True}))

            if is_layout:
                soup_for_extraction = BeautifulSoup(final_content, "html.parser")

                head_tag = soup_for_extraction.find("head")
                links_html = "\n".join(str(tag) for tag in head_tag.find_all("link")) if head_tag else ""

                # Helper to identify the special year script
                def is_year_script(tag):
                    return tag.name == 'script' and not tag.has_attr('src') and 'getFullYear' in (tag.string or '')

                # Collect all scripts EXCEPT the year script
                scripts_to_move = [
                    str(s) for s in soup_for_extraction.find_all("script") if not is_year_script(s)
                ]
                scripts_html = "\n".join(scripts_to_move)

                # CRUCIAL: Remove the moved scripts from the soup before extracting content
                for s in soup_for_extraction.find_all("script"):
                    if not is_year_script(s):
                        s.decompose()

                # Determine the base layout and extract the main content block
                template_name = "vertical.html"  # Default
                content_section = ""

                content_div = soup_for_extraction.find(attrs={"data-content": True})

                if content_div:
                    # Content is inside a specific div, use vertical or app layout
                    content_section = content_div.decode_contents().strip()
                    template_name = 'vertical.html'

                elif soup_for_extraction.body:
                    # Content is the entire body, use the base layout
                    content_section = soup_for_extraction.body.decode_contents().strip()
                    template_name = "base.html"

                # Rebuild the file with Django template inheritance
                django_template = f"""{{% extends 'layouts/{template_name}' %}}
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
                final_output = django_template.strip()
            else:
                final_output = final_content.strip()

            with open(file, "w", encoding="utf-8") as f:
                f.write(final_output + "\n")

            Log.converted(str(file))
            count += 1

        Log.info(f"{count} files converted in {self.project_pages_path}")

    def _generic_include_replacer(self, match: re.Match) -> str:
        """
        A robust callback function to replace any matched @@include directive
        with the correct Django {% include %} tag.
        """
        raw_path = match.group(1)
        data_str = match.group(2)

        clean_path = raw_path.lstrip("./")

        if data_str:
            data = self._extract_data_from_include(data_str)
            if data:
                with_parts = []
                for key, value in data.items():
                    escaped_value = str(value).replace("'", "\\'")
                    with_parts.append(f"{key}='{escaped_value}'")

                with_clause = " ".join(with_parts)
                return f"{{% include '{clean_path}' with {with_clause} %}}"

        return f"{{% include '{clean_path}' %}}"

    def _extract_data_from_include(self, data_str: str) -> dict:
        """
        Safely parses a string that represents a Python dictionary.
        """
        try:
            s = re.sub(r'[\n\r\t]', ' ', data_str)
            s = re.sub(r'\s{2,}', ' ', s)
            s = re.sub(r',\s*([}\]])', r'\1', s)
            return ast.literal_eval(s)
        except (ValueError, SyntaxError) as e:
            Log.warning(f"Could not parse include data: {data_str}. Error: {e}")
            return {}

    def _clean_static_paths(self, html: str) -> str:
        """
        Rewrites local asset paths in src and href to use the Django {% static %} tag.
        Handles paths with or without 'assets/' and ignores absolute URLs.
        """
        asset_extensions = [
            'js', 'css', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico',
            'webp', 'woff', 'woff2', 'ttf', 'eot', 'mp4', 'webm'
        ]
        extensions_pattern = '|'.join(asset_extensions)

        pattern = re.compile(
            r'\b(href|src)\s*=\s*["\']'
            r'(?!{{|#|https?://|//|mailto:|tel:)'  # Exclusions
            r'([^"\'#]+\.(?:' + extensions_pattern + r'))'  # Capture path
                                                     r'([^"\']*)'  # Capture query/fragment
                                                     r'["\']'
        )

        def replacer(match: re.Match) -> str:
            attr = match.group(1)
            path = match.group(2)
            query_fragment = match.group(3)

            # Normalize path: remove any leading directories including 'assets'
            normalized_path = re.sub(r'^(?:.*\/)?assets\/', '', path).lstrip('/')

            return f'{attr}="{{% static \'{normalized_path}\' %}}{query_fragment}"'

        return pattern.sub(replacer, html)

    def _replace_html_links_with_django_urls(self, html_content):
        """
        Replaces direct .html links in anchor tags (<a>) with Django {% url %} tags.
        Handles 'index.html' specifically to map to the root URL '/'.
        Example: <a href="dashboard-clinic.html"> -> <a href="{% url 'pages:dynamic_pages' template_name='dashboard-clinic' %}">
        Example: <a href="index.html"> -> <a href="/">
        """
        # Regex to find href attributes in <a> tags that end with .html
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

    def _replace_partial_variables(self):
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_partials_path.rglob(f"*{DJANGO_EXTENSION}"):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            new_content = pattern.sub(r'{{ \1 }}', content)
            if new_content != content:
                file.write_text(new_content, encoding="utf-8")
                Log.updated(str(file))
                count += 1

        if count:
            Log.info(f"{count} files updated in {self.project_partials_path}")
