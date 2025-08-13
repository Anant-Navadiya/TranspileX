import re
import json
import subprocess
import ast
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.config.base import FLASK_DESTINATION_FOLDER, FLASK_ASSETS_FOLDER, FLASK_PROJECT_CREATION_COMMAND, \
    FLASK_PROJECT_CREATION_COMMAND_AUTH, FLASK_GULP_ASSETS_PATH, FLASK_EXTENSION
from transpilex.helpers import change_extension_and_copy, copy_assets
from transpilex.helpers.add_gulpfile import add_gulpfile
from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.git import remove_git_folder
from transpilex.helpers.logs import Log
from transpilex.helpers.move_files import move_files
from transpilex.helpers.package_json import update_package_json
from transpilex.helpers.replace_html_links import replace_html_links


class FlaskConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True,
                 auth: bool = False):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(FLASK_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp

        self.project_root = Path(self.destination_path / project_name)
        self.project_assets_path = Path(self.project_root / FLASK_ASSETS_FOLDER)
        self.project_pages_path = Path(self.project_root / "apps" / "templates" / "pages")
        self.project_partials_path = Path(self.project_root / "apps" / "templates" / "partials")

        self.auth_required = auth

        self.create_project()

    def create_project(self):

        Log.project_start(self.project_name)

        try:
            self.project_root.mkdir(parents=True, exist_ok=True)

            subprocess.run(
                FLASK_PROJECT_CREATION_COMMAND_AUTH if self.auth_required else FLASK_PROJECT_CREATION_COMMAND,
                cwd=self.project_root, check=True,
                capture_output=True, text=True)

            Log.success("Flask project created successfully")

            remove_git_folder(self.project_root)

        except subprocess.CalledProcessError:
            Log.error("Flask project creation failed")
            return

        self.project_pages_path.mkdir(parents=True, exist_ok=True)

        change_extension_and_copy(FLASK_EXTENSION, self.source_path, self.project_pages_path)

        self._convert()

        move_files(Path(self.project_pages_path / "partials"), self.project_partials_path)

        self._replace_partial_variables()

        copy_assets(self.assets_path, self.project_assets_path)

        if self.include_gulp:
            add_gulpfile(self.project_root, FLASK_GULP_ASSETS_PATH)
            add_plugins_file(self.source_path, self.project_root)
            update_package_json(self.source_path, self.project_root, self.project_name)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):
        """
        Converts HTML files to Flask/Jinja2 template format, handling @@includes,
        static file paths, and HTML link replacements in a generic way.
        """
        count = 0
        for file in self.project_pages_path.rglob("*.html"):
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            # Step 1: Handle the special case for the main page title first.
            # Its data is extracted and used in the {% block title %}, and the include is removed.
            title_meta_pattern = re.compile(
                r'@@include\(\s*[\'"]\.\/partials\/(title-meta|app-meta-title)\.html[\'"]\s*,\s*(\{.*?\})\s*\)',
                re.DOTALL,
            )
            title_meta_match = title_meta_pattern.search(content)

            layout_title = "Untitled"  # Default title
            if title_meta_match:
                meta_data_str = title_meta_match.group(2)
                meta_data = self._extract_json_from_include(meta_data_str)
                # Look for common keys for a page title
                layout_title = meta_data.get("title", meta_data.get("pageTitle", "Untitled")).strip()
                # Remove the original @@include line
                content = title_meta_pattern.sub("", content, count=1)

            # Step 2: Generically replace all other @@include directives.
            generic_include_pattern = re.compile(
                r'@@include\(\s*[\'"](.+?)[\'"]\s*(?:,\s*(\{.*?\})\s*)?\)', re.DOTALL
            )
            content = generic_include_pattern.sub(self._generic_include_replacer, content)

            # Step 3: Clean all asset paths to use Jinja2's static syntax.
            content = self._clean_static_paths(content)

            # Step 4: Determine if the file is a full layout and wrap it with a base template.
            soup = BeautifulSoup(content, "html.parser")
            is_layout = bool(soup.find("body") or soup.find(attrs={"data-content": True}))

            if is_layout:
                soup_for_extraction = BeautifulSoup(content, "html.parser")

                links_html = "\n".join(str(tag) for tag in soup_for_extraction.find_all("link"))

                def is_year_inline_script(tag):
                    if tag.name != "script": return False
                    if tag.has_attr("src"): return False
                    text = (tag.string or tag.get_text() or "").strip()
                    return "document.write(new Date().getFullYear())" in text

                scripts_to_block = []
                for s in list(soup_for_extraction.find_all("script")):
                    if is_year_inline_script(s):
                        continue
                    scripts_to_block.append(str(s))
                    s.decompose()
                scripts_html = "\n".join(scripts_to_block)

                # Determine the correct base layout and content block
                template_name = "vertical.html"  # Default layout
                content_div = soup_for_extraction.find(attrs={"data-content": True})
                if content_div:
                    content_section = content_div.decode_contents().strip()
                    # You might add logic here to detect which base layout to use
                    # For example, by checking for 'app-wrap' vs 'wrapper' classes.
                    if soup_for_extraction.find(class_='app-wrap'):
                        template_name = 'app.html'  # Assuming you have an app.html layout
                    else:
                        template_name = 'vertical.html'
                elif soup_for_extraction.body:
                    content_section = soup_for_extraction.body.decode_contents().strip()
                    template_name = "base.html"  # For standalone pages like auth
                else:
                    content_section = soup_for_extraction.decode_contents().strip()
                    template_name = "base.html"

                django_template = f"""{{% extends 'layouts/{template_name}' %}}

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
                # For partials that are not layouts, just use the processed content
                final_output = content.strip()

            # Step 5: Replace .html links
            final_output = replace_html_links(final_output, "")

            with open(file, "w", encoding="utf-8") as f:
                f.write(final_output + "\n")

            Log.converted(str(file))
            count += 1

        Log.info(f"{count} files converted in {self.project_pages_path}")

    def _generic_include_replacer(self, match: re.Match) -> str:
        """
        Callback function to replace a matched @@include directive with the
        correct Jinja2 {% include %} tag.
        """
        raw_path = match.group(1)
        json_str = match.group(2)

        # Normalize path: remove './' and leading slashes
        clean_path = raw_path.lstrip("./")

        # Special case: remove footer-scripts.html to avoid duplicate scripts,
        # assuming they are already in the base layout's script block.
        if "partials/footer-scripts.html" in clean_path:
            return ""

        # Handle includes that pass data
        if json_str:
            data = self._extract_json_from_include(json_str)
            if data:
                # Format key-value pairs for the 'with' clause
                # json.dumps ensures values are correctly formatted as JSON literals (e.g., strings, numbers, booleans)
                with_parts = [f"{key}={json.dumps(value, ensure_ascii=False)}" for key, value in data.items()]
                with_clause = " ".join(with_parts)
                return f"{{% include '{clean_path}' with {with_clause} %}}"

        # Handle includes without data or with invalid data
        return f"{{% include '{clean_path}' %}}"

    def _extract_json_from_include(self, data_str: str) -> dict:
        """
        Safely parses a string that represents a Python dictionary. It cleans up
        newlines within string values, extra whitespace, and trailing commas.
        """
        try:
            # 1. Replace all newline, tab, and carriage return characters with a space.
            #    This is the key fix for handling multi-line string values.
            s = re.sub(r'[\n\r\t]', ' ', data_str)

            # 2. Collapse multiple spaces into a single space for cleanliness.
            s = re.sub(r'\s{2,}', ' ', s)

            # 3. Remove trailing commas before a closing brace `}` or bracket `]`.
            s = re.sub(r',\s*([}\]])', r'\1', s)

            # 4. Now, safely evaluate the cleaned string.
            return ast.literal_eval(s)
        except (ValueError, SyntaxError):
            # This will log the original, problematic string for easier debugging.
            Log.warning(f"Could not parse include data: {data_str}")
            return {}

    def _replace_page_title_include(self, content):
        # This version matches single or double quotes and captures flexible spacing
        pattern = r'@@include\(\s*[\'"]\.\/partials\/page-title\.html[\'"]\s*,\s*(\{.*?\})\s*\)'

        def replacer(match):
            data = self._extract_json_from_include(match.group(1))  # match.group(1) gives the JSON directly
            title = data.get("title", "").strip()
            subtitle = data.get("subtitle", "").strip()
            return self._format_django_include(title=title, subtitle=subtitle)

        return re.sub(pattern, replacer, content)

    def _format_django_include(self, title=None, subtitle=None):
        parts = []
        if title:
            parts.append(f"title='{title}'")
        if subtitle:
            parts.append(f"subtitle='{subtitle}'")
        if parts:
            return f"{{% include 'partials/page-title.html' with {' '.join(parts)} %}}"
        return ""

    def _clean_static_paths(self, html: str) -> str:
        """
        Rewrites local asset paths in src, href, and xlink:href attributes
        to use the Flask/Jinja2 static file syntax.
        """
        # A list of common file extensions for static assets.
        asset_extensions = [
            'js', 'css', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico',
            'webp', 'woff', 'woff2', 'ttf', 'eot', 'mp4', 'webm', 'json'
        ]
        extensions_pattern = '|'.join(asset_extensions)

        pattern = re.compile(
            r'\b(href|src|xlink:href)\s*=\s*["\']'
            r'(?!{{|#|https?://|//|mailto:|tel:)'
            r'([^"\'#]+\.(?:' + extensions_pattern + r'))'
                                                     r'([^"\']*)'
                                                     r'["\']'
        )

        def replacer(match: re.Match) -> str:
            """This function is called for each found asset path."""
            attr = match.group(1)
            path = match.group(2)
            query_fragment = match.group(3)

            # If the path contains 'assets/', strip everything up to and including it.
            normalized_path = re.sub(r'^(?:.*\/)?assets\/', '', path)

            # Reconstruct the full attribute with the Jinja2 root path
            return f'{attr}="{{{{ config.ASSETS_ROOT }}}}/{normalized_path}{query_fragment}"'

        return pattern.sub(replacer, html)

    def _replace_partial_variables(self):
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_partials_path.rglob(f"*{FLASK_EXTENSION}"):
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
