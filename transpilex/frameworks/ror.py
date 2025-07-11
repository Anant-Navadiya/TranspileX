import os
import re
import json
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
import shutil

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, ROR_DESTINATION_FOLDER, ROR_ASSETS_FOLDER, ROR_EXTENSION
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.messages import Messenger
from transpilex.helpers.restructure_files import restructure_files


class RoRConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=ROR_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / ROR_ASSETS_FOLDER
        self.project_views_path = self.project_root / "app" / "views"
        self.project_controllers_path = self.project_root / "app" / "controllers"
        self.project_routes_path = self.project_root / "config" / "routes.rb"

        self.create_project()

    def create_project(self):

        Messenger.info(f"Creating RoR project at: '{self.project_root}'...")

        self.project_root.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(f'rails new {self.project_root}', shell=True, check=True)
            Messenger.success(f"RoR project created.")
        except subprocess.CalledProcessError:
            Messenger.error(f"RoR project creation failed.")
            return

        empty_folder_contents(self.project_views_path)

        restructure_files(self.source_path, self.project_views_path, new_extension=ROR_EXTENSION,
                          skip_dirs=['partials'], keep_underscore=True)

        self._convert()

        self._create_controllers(ignore_list=["layouts", "partials"])

        # update_package_json(self.source_path, self.project_root, self.project_name)

        Messenger.completed(f"Project '{self.project_name}' setup", str(self.project_root))

    def _convert(self):
        """
        Converts HTML files with custom @@include statements into Ruby on Rails ERB views.
        """
        count = 0

        for file in self.project_views_path.rglob(f"*.html.erb"):
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content
            soup_original = BeautifulSoup(original_content, 'html.parser')

            # --- Extract and remove page-title include ---
            page_title_render_string = ""
            page_title_include_params = {}
            title_from_page_title_include = None

            # Pattern to find @@include for page-title.html and capture its parameters
            page_title_pattern = r'(@@include\(\s*["\']\.?\/?partials\/page-title\.html["\']\s*,\s*(\{[\s\S]*?\})\s*\))'
            page_title_match = re.search(page_title_pattern, original_content, flags=re.DOTALL)

            if page_title_match:
                full_include_string = page_title_match.group(1)  # The entire @@include(...) string
                params_str = page_title_match.group(2)  # Just the parameters part (e.g., {"title": "Calendar"})

                page_title_include_params = self._extract_params_from_include(params_str)

                if page_title_include_params:
                    def ruby_value(v):
                        if isinstance(v, str):
                            escaped = v.replace('\\', '\\\\\\\\').replace('"', '\\"')
                            return f'"{escaped}"'
                        elif isinstance(v, bool):
                            return 'true' if v else 'false'
                        elif v is None:
                            return 'nil'
                        else:
                            return str(v)

                    params_str_ruby = ", ".join(f"{k}: {ruby_value(v)}" for k, v in page_title_include_params.items())
                    page_title_render_string = f"<%= render 'layouts/partials/page_title', {params_str_ruby} %>\n\n"

                    if "title" in page_title_include_params:
                        title_from_page_title_include = page_title_include_params["title"]

                content = content.replace(full_include_string, "")

            # --- Handle generic partials with params (except page-title) ---
            pattern_all_partials_with_params = r'@@include\(\s*["\']\.?\/?partials\/(?!page-title\.html)([^"\']+\.html)["\']\s*,\s*(\{(?:[^{}]|\{[^{}]*\})*\})\s*\)'
            matches = re.findall(pattern_all_partials_with_params, content, flags=re.DOTALL)

            generic_partials_render_strings = []

            for partial_name_html, params_str in matches:
                partial_name = partial_name_html.replace('.html', '')
                params_dict = self._extract_params_from_include(params_str)

                if params_dict:
                    def ruby_value(v):
                        if isinstance(v, str):
                            escaped = v.replace('\\', '\\\\\\\\').replace('"', '\\"')
                            return f'"{escaped}"'
                        elif isinstance(v, bool):
                            return 'true' if v else 'false'
                        elif v is None:
                            return 'nil'
                        else:
                            return str(v)

                    params_str_ruby = ", ".join(f"{k}: {ruby_value(v)}" for k, v in params_dict.items())
                    render_str = f"<%= render 'layouts/partials/{partial_name}', {params_str_ruby} %>\n\n"
                else:
                    render_str = f"<%= render 'layouts/partials/{partial_name}' %>\n\n"

                generic_partials_render_strings.append(render_str)

                # Remove the matched include statement from content
                # Use re.escape on params_str to safely remove it
                pattern_remove = re.escape(f'@@include("partials/{partial_name_html}", {params_str})')
                content = re.sub(pattern_remove, '', content, flags=re.DOTALL)

            # Append all generic partial renders after page-title render
            page_title_render_string += "".join(generic_partials_render_strings)

            # --- Determine the main page title for @title ERB variable ---
            title = title_from_page_title_include or self._extract_title_from_soup_or_data(
                soup_original) or "Page Title"

            erb_header = f"<% @title = \"{title}\" %>\n\n"

            # --- Convert all other @@include statements (excluding page-title.html) ---
            content = self._convert_general_includes(content)

            # --- Extract main content ---
            soup_current = BeautifulSoup(content, 'html.parser')
            main_content = self._extract_main_content(soup_current, content)

            # --- Convert image paths ---
            main_content = self._convert_image_paths(main_content)

            # --- Extract script tags ---
            vite_scripts = self._extract_vite_scripts(soup_original)

            # --- Remove script tags ---
            main_content = self._remove_script_tags(main_content)

            # --- Compose final ERB output ---
            erb_output = (
                    erb_header +
                    page_title_render_string +
                    main_content.strip() +
                    "\n\n<% content_for :javascript do %>\n"
            )

            for script in vite_scripts:
                erb_output += f"  <%= vite_javascript_tag '{script}' %>\n"
            erb_output += "<% end %>\n"

            with open(file, "w", encoding="utf-8") as f:
                f.write(erb_output)

            Messenger.success(f"Converted Rails view: {file.relative_to(self.project_views_path)}")
            count += 1

        Messenger.success(f"\n{count} Rails view files converted successfully.")

    def _extract_all_partials_with_params(self, content):
        """
        Finds all @@include("partials/partial_name.html", {...}) with params,
        returns list of tuples: (full_include_string, partial_name, params_dict)
        """
        results = []

        # Regex to find all @@include statements with params JSON (non-greedy, multiline safe)
        pattern = r'@@include\(\s*["\']\.?\/?partials\/([^"\']+\.html)["\']\s*,\s*(\{(?:[^{}]|\{[^{}]*\})*\})\s*\)'

        for match in re.finditer(pattern, content, flags=re.DOTALL):
            full_include = match.group(0)
            partial_filename = match.group(1)  # e.g. 'menu.html'
            params_str = match.group(2)

            # Extract partial name without extension
            partial_name = partial_filename.replace('.html', '')

            # Parse params
            params_dict = self._extract_params_from_include(params_str)

            results.append((full_include, partial_name, params_dict))

        return results

    def _extract_page_title_include(self, content):
        """
        Extract the full @@include(...) string and the JSON params for page-title.html
        using manual brace counting for multiline and nested braces.
        Returns (full_include_string, params_str) or (None, None) if not found.
        """
        pattern_start = r'@@include\(\s*["\']\.?\/?partials\/page-title\.html["\']\s*,'
        match_start = re.search(pattern_start, content)
        if not match_start:
            return None, None

        start_pos = match_start.end()  # position right after the comma
        # Skip whitespace to find first '{'
        while start_pos < len(content) and content[start_pos] not in '{':
            start_pos += 1
        if start_pos >= len(content) or content[start_pos] != '{':
            return None, None

        brace_count = 0
        end_pos = start_pos
        while end_pos < len(content):
            if content[end_pos] == '{':
                brace_count += 1
            elif content[end_pos] == '}':
                brace_count -= 1
                if brace_count == 0:
                    break
            end_pos += 1

        if brace_count != 0:
            return None, None

        params_str = content[start_pos:end_pos + 1]
        # full include string ends at position after the closing brace + 1 for ')'
        full_include_string = content[match_start.start():end_pos + 2]  # includes final '})'

        return full_include_string, params_str

    def _convert_general_includes(self, content):
        pattern_general = r'@@include\(\s*["\']\.?\/partials\/(?!page-title\.html)([^"\']+)["\'](?:\s*,\s*(array\(.*?\)|\{.*?\}))?\s*\)'

        def general_replacer(m):
            partial_name = m.group(1).replace('.html', '')
            return f"<%= render 'layouts/partials/{partial_name}' %>"

        content = re.sub(pattern_general, general_replacer, content, flags=re.DOTALL)
        return content

    def _extract_params_from_include(self, params_str):
        # First, clean string to valid JSON format
        # Remove newlines inside quoted strings by replacing them with spaces

        # Regex to find multiline strings in quotes and replace newlines with space
        def replace_newlines_in_quotes(match):
            s = match.group(0)
            # Replace newlines and tabs with space, then collapse multiple spaces into one
            s = s.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
            s = re.sub(r'\s+', ' ', s)
            return s

        # Apply to all double-quoted strings
        params_str = re.sub(r'"([^"]*?)"', replace_newlines_in_quotes, params_str)

        # Now do your existing JSON cleanup and parse
        try:
            json_str_cleaned = params_str.replace("'", '"')
            json_str_cleaned = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str_cleaned)
            return json.loads(json_str_cleaned)
        except json.JSONDecodeError:
            Messenger.warning(f"Failed to parse as JSON: {params_str[:50]}...")
            pass

        params_dict = {}
        param_pattern = re.compile(r"""
            (?:['"]?(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)['"]?\s*=>\s*)?
            (?:
                ['"](?P<sval>(?:\\.|[^'"])*)['"]
                |
                (?P<nval>-?\d+(?:\.\d+)?)
                |
                (?P<bool>true|false)
                |
                (?P<null>null)
            )
            \s*(?:,\s*|$)
        """, re.VERBOSE | re.DOTALL)

        for match in param_pattern.finditer(params_str):
            key = match.group('key')
            if not key:
                continue

            if match.group('sval') is not None:
                value = match.group('sval').replace('\\"', '"').replace("\\'", "'")
            elif match.group('nval') is not None:
                value = float(match.group('nval')) if '.' in match.group('nval') else int(match.group('nval'))
            elif match.group('bool') is not None:
                value = True if match.group('bool') == 'true' else False
            elif match.group('null') is not None:
                value = None
            else:
                value = None

            params_dict[key] = value

        if not params_dict:
            Messenger.warning(f"Could not extract parameters from: {params_str[:50]}...")
        return params_dict

    def _extract_title_from_soup_or_data(self, soup):
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        data_title_elem = soup.find(attrs={"data-title": True})
        if data_title_elem:
            return data_title_elem["data-title"].strip()

        return None

    def _extract_main_content(self, soup, original_content_fallback):
        content_div = soup.find(attrs={"data-content": True})
        if content_div:
            return ''.join(str(c) for c in content_div.contents)

        if soup.body:
            return ''.join(str(c) for c in soup.body.contents)

        return original_content_fallback

    def _remove_script_tags(self, content_html):
        soup = BeautifulSoup(content_html, 'html.parser')
        for script in soup.find_all('script'):
            script.decompose()
        return str(soup)

    def _convert_image_paths(self, content_html):
        soup = BeautifulSoup(content_html, 'html.parser')
        placeholders = {}

        for i, img_tag in enumerate(soup.find_all('img')):
            src = img_tag.get('src')
            if not src:
                continue

            normalized_image_path = None
            if src.startswith('assets/images/'):
                normalized_image_path = src.replace('assets/', '')
            elif src.startswith('images/'):
                normalized_image_path = src

            if normalized_image_path:
                # Escape single quotes inside path just in case (usually not needed)
                safe_path = normalized_image_path.replace("'", "\\'")

                erb_tag = f'<%= vite_asset_path \'{safe_path}\' %>'
                placeholder = f"@@ERB_PLACEHOLDER_{i}@@"
                placeholders[placeholder] = erb_tag

                # Set src attribute to the placeholder (which is safe text)
                img_tag['src'] = placeholder

        # Serialize to string: placeholders prevent escaping ERB tags
        html_with_placeholders = str(soup)

        # Replace placeholders with ERB tags (quoted properly)
        for placeholder, erb_tag in placeholders.items():
            # Replace the placeholder with the ERB tag surrounded by quotes (HTML attribute safe)
            html_with_placeholders = html_with_placeholders.replace(
                placeholder,
                erb_tag
            )

        Messenger.info(f"Image ERB replacement done, ERB tags present? {'<%=' in html_with_placeholders}")

        return html_with_placeholders

    def _extract_vite_scripts(self, soup):
        vite_scripts = []
        for script in soup.find_all('script'):
            src = script.get('src')
            if not src:
                continue
            normalized_src = src.lstrip('/').replace('assets/', '')
            vite_scripts.append(normalized_src)
        return vite_scripts

    def _create_controller_file(self, path, controller_name, actions):
        """
        Creates a Rails controller Ruby file with appropriate action methods.
        """
        class_name = f"{controller_name.capitalize()}Controller"

        methods = ""
        for action_name, template_path, nested in actions:
            methods += f"  def {action_name}\n"
            if nested:
                methods += f"    render template: \"{template_path}\"\n"
            methods += "  end\n\n"

        controller_code = f"""class {class_name} < ApplicationController
    {methods.strip()}
    end
    """

        with open(path, "w", encoding="utf-8") as f:
            f.write(controller_code)

    def _create_controllers(self, ignore_list=None):
        ignore_list = ignore_list or []

        if os.path.isdir(self.project_controllers_path):
            shutil.rmtree(self.project_controllers_path)
        os.makedirs(self.project_controllers_path, exist_ok=True)

        controllers_actions = {}

        for controller_name in os.listdir(self.project_views_path):
            if controller_name in ignore_list:
                continue
            controller_folder_path = os.path.join(self.project_views_path, controller_name)
            if not os.path.isdir(controller_folder_path):
                continue

            actions = []

            for root, dirs, files in os.walk(controller_folder_path):
                dirs[:] = [d for d in dirs if d not in ignore_list]

                for file in files:
                    if file in ignore_list:
                        continue
                    if file.endswith(".html.erb") and not file.startswith("_"):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, self.project_views_path)
                        rel_path_no_ext = rel_path[:-len(".html.erb")]
                        parts = rel_path_no_ext.split(os.sep)
                        nested = len(parts) > 2
                        action_name = "_".join(parts[1:]) if nested else parts[1]
                        template_path = rel_path_no_ext.replace(os.sep, "/")
                        actions.append((action_name, template_path, nested))

            if actions:
                controller_file_name = f"{controller_name}_controller.rb"
                controller_file_path = os.path.join(self.project_controllers_path, controller_file_name)
                self._create_controller_file(controller_file_path, controller_name, actions)
                controllers_actions[controller_name] = actions
                Messenger.success(f"Created: {controller_file_path}")

        self._create_routes(controllers_actions)
        Messenger.success("Controller and routes generation completed.")

    def _create_routes(self, controllers_actions):
        """
        Generate Rails 'get' routes and append to routes.rb

        :param controllers_actions: Dict with controller_name as key, and list of (action_name, template_path, nested) tuples as value
        """
        route_lines = []

        for controller_name, actions in controllers_actions.items():
            for action_name, template_path, nested in actions:
                if "_" in action_name:
                    # Nested action: replace underscores with dashes in URL path
                    url_path_action = action_name.replace("_", "-")
                    url_path = f"{controller_name}/{url_path_action}"
                    route_line = f'get "{url_path}", to: \'{controller_name}#{action_name}\''
                else:
                    # Flat action: simple route without `to:`
                    url_path = f"{controller_name}/{action_name}"
                    route_line = f'get "{url_path}"'

                route_lines.append(route_line)

        with open(self.project_routes_path, "a", encoding="utf-8") as f:
            for line in route_lines:
                f.write(line + "\n")

        Messenger.success(f"Routes appended to {self.project_routes_path}")
