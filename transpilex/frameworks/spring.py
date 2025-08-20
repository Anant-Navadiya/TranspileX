import os
import re
import ast
import shutil
import requests, zipfile, io
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.config.base import SPRING_BOOT_DESTINATION_FOLDER, \
    SPRING_BOOT_PROJECT_CREATION_URL, SPRING_BOOT_PROJECT_PARAMS, \
    SPRING_BOOT_GULP_ASSETS_PATH, SPRING_BOOT_EXTENSION, SPRING_JAVA_SOURCE_FOLDER, SPRING_RESOURCES_FOLDER, \
    SPRING_TEMPLATES_FOLDER, SPRING_BOOT_ASSETS_FOLDER, SPRING_BOOT_GROUP_ID
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.restructure_files import restructure_files
from transpilex.helpers import copy_assets
from transpilex.helpers.plugins_file import plugins_file
from transpilex.helpers.gulpfile import add_gulpfile
from transpilex.helpers.logs import Log
from transpilex.helpers.package_json import update_package_json
from transpilex.helpers.validations import folder_exists


class SpringConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(SPRING_BOOT_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp

        self.project_root = self.destination_path / project_name
        self.project_java_path = self.project_root / SPRING_JAVA_SOURCE_FOLDER
        self.project_resources_path = self.project_root / SPRING_RESOURCES_FOLDER
        self.project_templates_path = self.project_resources_path / SPRING_TEMPLATES_FOLDER
        self.project_assets_path = self.project_resources_path / SPRING_BOOT_ASSETS_FOLDER
        self.project_controllers_path = self.project_java_path / SPRING_BOOT_GROUP_ID / self.project_name / "controller"
        self.project_partials_path = self.project_templates_path / "partials"

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        params = {
            **SPRING_BOOT_PROJECT_PARAMS,
            "baseDir": self.project_name,
            "artifactId": self.project_name,
            "name": self.project_name,
            "packageName": f"com.{self.project_name}",
        }

        try:
            r = requests.get(SPRING_BOOT_PROJECT_CREATION_URL, params=params, timeout=10)
            r.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                z.extractall(self.destination_path)

            Log.success("Spring Boot project created successfully")

        except requests.exceptions.RequestException as e:
            Log.error(f"Network or request error: {e}")

        except zipfile.BadZipFile:
            Log.error("Downloaded file is not a valid ZIP archive")

        except OSError as e:
            Log.error(f"File system error while extracting: {e}")

        except Exception as e:
            Log.error(f"Unexpected error: {e}")

        restructure_files(self.source_path, self.project_templates_path, new_extension=SPRING_BOOT_EXTENSION,
                          ignore_list=['partials'])

        self._copy_partials()

        self._convert()

        self._create_controllers(ignore_list=["layouts", "partials"])

        copy_assets(self.assets_path, self.project_assets_path)

        if self.include_gulp:
            has_plugins_file = plugins_file(self.source_path, self.project_root)
            add_gulpfile(self.project_root, SPRING_BOOT_GULP_ASSETS_PATH, has_plugins_file)
            update_package_json(self.source_path, self.project_root, self.project_name)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):
        """Processes all .html files, dispatching to page or partial processor."""
        count = 0
        all_files = list(self.project_templates_path.rglob("*.html"))

        for file in all_files:
            is_partial = 'partials' in file.parts or file.name.startswith('_')
            if is_partial:
                self._process_partial_file(file)
            else:
                self._process_page_file(file)
            count += 1
        Log.info(f"{count} files converted in {self.project_templates_path}")

    def _format_thymeleaf_value(self, value):
        """Formats a Python value into a Thymeleaf-compatible string for a fragment parameter."""
        if isinstance(value, str):
            escaped = value.replace("'", "\\'")
            return f"'{escaped}'"
        elif isinstance(value, bool):
            return 'true' if value else 'false'
        elif value is None:
            return 'null'
        else:
            return str(value)

    def _extract_params_from_include(self, params_str: str) -> dict:
        if not params_str or not params_str.strip():
            return {}
        eval_str = params_str.strip()
        eval_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', eval_str)
        eval_str = eval_str.replace('true', 'True').replace('false', 'False').replace('null', 'None')
        eval_str = re.sub(r',\s*([}\]])', r'\1', eval_str)
        try:
            return ast.literal_eval(eval_str)
        except (ValueError, SyntaxError) as e:
            Log.warning(f"Failed to parse parameters: {params_str[:70]}... Error: {e}")
            return {}

    def _convert_includes_to_thymeleaf(self, content: str) -> str:
        """Finds all @@include statements and replaces them with Thymeleaf th:replace fragments."""
        include_pattern = re.compile(
            r'@@include\(\s*["\']([^"\']+)["\']\s*(?:,\s*(\{[\s\S]*?\}))?\s*\)',
            re.DOTALL
        )

        def replacer(match):
            path_str = match.group(1)
            params_str = match.group(2)

            clean_path = path_str.strip().replace('./', '').replace('.html', '')
            fragment_name = Path(clean_path).name

            # Thymeleaf fragment path: "partials/page-title" -> "~{partials/page-title :: page-title}"
            thymeleaf_path = f"~{{{clean_path} :: {fragment_name}}}"

            if not params_str:
                return f'<th:block th:replace="{thymeleaf_path}" />'

            params_dict = self._extract_params_from_include(params_str)
            if not params_dict:
                return f'<th:block th:replace="{thymeleaf_path}" />'

            # Convert Python dict to Thymeleaf parameters: (key='value', key2=123)
            thymeleaf_params = ", ".join(
                f"{key}={self._format_thymeleaf_value(value)}"
                for key, value in params_dict.items()
            )

            return f'<th:block th:replace="{thymeleaf_path}({thymeleaf_params})" />'

        return include_pattern.sub(replacer, content)

    def _prepare_content_placeholders(self, soup_element):
        """
        Converts .html page links into root-relative hrefs,
        turning hyphens and underscores into URL path separators.
        """
        for a_tag in soup_element.find_all('a', href=True):
            href = a_tag.get('href')
            if href and href.endswith('.html') and not href.startswith(('http', '#', 'javascript:')):
                url_path = href.replace('.html', '').replace('_', '/').replace('-', '/')

                a_tag['href'] = f'/{url_path}'

        return soup_element

    def _process_page_file(self, file_path):
        """
        Extracts content and assets from a template file and wraps them in a
        clean Thymeleaf layout with proper formatting.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        content = clean_relative_asset_paths(content)

        page_meta_fragment = ""
        title = "Page Title"
        title_meta_pattern = re.compile(
            r'@@include\(\s*["\']\./partials/([^"\']*?meta-title[^"\']*?|[^"\']*?title-meta[^"\']*?)\.html["\']\s*,\s*(\{[\s\S]*?\})\s*\)',
            re.DOTALL
        )
        match = title_meta_pattern.search(content)
        if match:
            params_dict = self._extract_params_from_include(match.group(2))
            title = params_dict.get('title', params_dict.get('pageTitle', title))
            page_meta_fragment = f"<th:block layout:fragment=\"page-meta\" th:replace=\"~{{partials/page-meta :: page-meta('{title}')}}\" />"

        # Parse the entire file ONCE
        soup = BeautifulSoup(content, 'html.parser')

        # Extract ALL styles and scripts from the entire file first.
        # This ensures we find them no matter where they are located.
        styles = self._extract_styles(soup, soup)
        scripts = self._extract_scripts(soup, soup)

        # Now, find the content block from the modified soup (which no longer has those assets)
        layout_name = 'vertical'
        content_source = soup.find(attrs={"data-content": True})
        if content_source is None:
            if soup.body:
                content_source = soup.body
                layout_name = 'base'
            else:
                Log.warning(f"No content block ('data-content' or 'body') found in {file_path}. Skipping.")
                return

        # Process the content block's inner HTML
        content_html = content_source.decode_contents()
        processed_content_html = self._convert_includes_to_thymeleaf(content_html)
        temp_soup = BeautifulSoup(processed_content_html, 'html.parser')
        final_content_soup = self._prepare_content_placeholders(temp_soup)
        final_content = final_content_soup.decode(formatter=None)

        # Assemble the final template with newline-separated assets
        thymeleaf_output = f"""<html xmlns:layout="http://www.ultraq.net.nz/thymeleaf/layout" layout:decorate="~{{layouts/{layout_name}}}">

<th:block layout:fragment="styles">
    {'\n    '.join(styles)}
</th:block>

<head>
    {page_meta_fragment}
</head>

<body>
    <th:block layout:fragment="content">
        {final_content.strip()}
    </th:block>

    <th:block layout:fragment="scripts">
        {'\n    '.join(scripts)}
    </th:block>
</body>

</html>"""

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(thymeleaf_output)
        Log.converted(str(file_path))

    def _process_partial_file(self, file_path):
        """
        Converts a partial file into a full HTML document containing a named
        Thymeleaf fragment.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Clean asset paths and convert includes as before
        content = clean_relative_asset_paths(content)
        content = self._convert_includes_to_thymeleaf(content)

        # Parse the content to process placeholders (like hrefs)
        temp_soup = BeautifulSoup(content, 'html.parser')
        processed_soup = self._prepare_content_placeholders(temp_soup)
        processed_content = processed_soup.decode(formatter=None).strip()

        # Derive the fragment name from the file name (e.g., "sidenav")
        fragment_name = file_path.stem.replace('_', '')

        final_output = f"""<!DOCTYPE html>
<html xmlns:th="http://www.thymeleaf.org">
<th:block th:fragment="{fragment_name}">

{processed_content}

</th:block>
</html>"""

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_output)
        Log.converted(str(file_path))

    def _create_controller_file(self, path, controller_name, actions):
        """Creates a Spring Boot controller Java file with nested routes."""
        class_name = controller_name.capitalize()
        request_mapping = controller_name.lower()

        methods = ""
        for action_name, template_path in actions:
            method_name = self._to_camel_case(action_name)

            get_mapping = action_name.replace('_', '/').replace('-', '/')

            if get_mapping == 'index':
                get_mapping = ""

            methods += f"""
@GetMapping("/{get_mapping}")
public String {method_name}() {{
    return "{template_path}";
}}
    """
        package_name = str(self.project_controllers_path.relative_to(self.project_java_path)).replace(os.sep, '.')
        controller_code = f"""package {package_name};

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;

@Controller
@RequestMapping("/{request_mapping}")
public class {class_name} {{
    {methods.strip()}
}}
    """
        with open(path, "w", encoding="utf-8") as f:
            f.write(controller_code)

    def _create_controllers(self, ignore_list=None):
        """Scans the template directory to generate controllers and their methods."""
        ignore_list = ignore_list or []
        if os.path.isdir(self.project_controllers_path):
            shutil.rmtree(self.project_controllers_path)
        os.makedirs(self.project_controllers_path, exist_ok=True)

        for controller_name in os.listdir(self.project_templates_path):
            if controller_name in ignore_list:
                continue

            controller_folder_path = os.path.join(self.project_templates_path, controller_name)
            if not os.path.isdir(controller_folder_path):
                continue

            actions = []
            for root, _, files in os.walk(controller_folder_path):
                for file in files:
                    if file.endswith(SPRING_BOOT_EXTENSION) and not file.startswith("_"):
                        full_path = Path(root) / file
                        rel_path = full_path.relative_to(self.project_templates_path)

                        template_path = str(rel_path.with_suffix('')).replace(os.sep, '/')

                        # Action name is the file path relative to its controller folder
                        action_name = str(full_path.relative_to(controller_folder_path).with_suffix('')).replace(
                            os.sep, '_')

                        actions.append((action_name, template_path))

            if actions:
                controller_file_name = f"{controller_name.capitalize()}.java"
                controller_file_path = self.project_controllers_path / controller_file_name
                self._create_controller_file(controller_file_path, controller_name, actions)
                Log.created(str(controller_file_path))
        Log.info("Controller generation completed")

    def _copy_partials(self):
        """Copies partials from source to the templates/partials directory."""
        self.project_partials_path.mkdir(parents=True, exist_ok=True)
        partials_source = self.source_path / "partials"
        if partials_source.exists() and partials_source.is_dir():
            for item in os.listdir(partials_source):
                source_item = partials_source / item
                dest_item = self.project_partials_path / item
                if source_item.is_file():
                    shutil.copy2(source_item, dest_item)

    def _to_camel_case(self, snake_str):
        """Converts snake_case or kebab-case to camelCase."""
        components = snake_str.replace('-', '_').split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

    def _extract_styles(self, element_to_search, soup_factory):
        """Extracts local stylesheet <link> tags."""
        styles = []
        # Iterate over a static list copy and add a check for None
        for link_tag in list(element_to_search.find_all('link', rel='stylesheet')):
            if link_tag:
                href = link_tag.get('href')
                if href and not href.startswith(('http', '//')):
                    new_tag = soup_factory.new_tag('link', rel='stylesheet', href=href)
                    styles.append(str(new_tag))
                    link_tag.decompose()
        return styles

    def _extract_scripts(self, element_to_search, soup_factory):
        """Extracts local script tags."""
        scripts = []
        # Iterate over a static list copy and add a check for None
        for script in list(element_to_search.find_all('script')):
            if script:
                src = script.get('src')
                if src and not src.startswith(('http', '//')):
                    new_tag = soup_factory.new_tag('script', src=src)
                    scripts.append(str(new_tag))
                    script.decompose()
        return scripts
