import os
import re
import ast
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup
import shutil

from transpilex.config.base import ROR_DESTINATION_FOLDER, ROR_ASSETS_FOLDER, ROR_EXTENSION, \
    ROR_PROJECT_CREATION_COMMAND, ROR_ASSETS_PRESERVE
from transpilex.helpers import copy_assets, change_extension_and_copy
from transpilex.helpers.copy_assets import copy_assets_in_public
from transpilex.helpers.git import remove_git_folder
from transpilex.helpers.logs import Log
from transpilex.helpers.package_json import sync_package_json
from transpilex.helpers.restructure_files import restructure_files
from transpilex.helpers.validations import folder_exists


class RoRConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(ROR_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = Path(self.project_root / ROR_ASSETS_FOLDER)
        self.project_views_path = Path(self.project_root / "app" / "views")
        self.project_partials_path = Path(self.project_views_path / "partials")
        self.project_controllers_path = Path(self.project_root / "app" / "controllers")
        self.project_routes_path = self.project_root / "config" / "routes.rb"

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
            self.project_root.mkdir(parents=True, exist_ok=True)

            subprocess.run(ROR_PROJECT_CREATION_COMMAND, cwd=self.project_root, check=True, capture_output=True,
                           text=True)

            Log.success("RoR project created successfully")

            remove_git_folder(self.project_root)

        except subprocess.CalledProcessError:
            Log.error("RoR project creation failed")
            return

        restructure_files(self.source_path, self.project_views_path, new_extension=ROR_EXTENSION,
                          ignore_list=['partials'], keep_underscore=True)

        self._copy_partials()

        self._convert()

        self._replace_partial_variables()

        self._create_controllers(ignore_list=["layouts", "partials"])

        public_only = copy_assets_in_public(self.assets_path, Path(self.project_root / "public"),
                                            ["media", "data", "json"])

        copy_assets(
            self.assets_path,
            self.project_assets_path,
            preserve=ROR_ASSETS_PRESERVE,
            exclude=public_only
        )

        sync_package_json(self.source_path, self.project_root)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):
        """
        Processes all .html.erb files, dispatching them to the correct
        processor (page or partial) based on their path.
        """
        count = 0
        all_files = list(self.project_views_path.rglob("*.html.erb"))

        for file in all_files:
            # A file is considered a partial if it's inside a 'partials' directory
            # or if its name starts with an underscore.
            is_partial = 'partials' in file.parts or file.name.startswith('_')

            if is_partial:
                self._process_partial_file(file)
            else:
                self._process_page_file(file)

            count += 1

        Log.info(f"{count} files converted in {self.project_views_path}")

    def _format_ruby_value(self, value):
        """Formats a Python value into a Ruby-compatible string for a hash."""
        if isinstance(value, str):
            # Escape backslashes and double quotes, then wrap the result in double quotes.
            escaped = value.replace('\\', '\\\\').replace('"', '\\"')
            return f'"{escaped}"'
        elif isinstance(value, bool):
            return 'true' if value else 'false'
        elif value is None:
            return 'nil'
        else:
            return str(value)

    def _extract_params_from_include(self, params_str: str) -> dict:
        """
        Safely parses a JS-object-like string into a Python dictionary
        using ast.literal_eval for robustness with quotes and data types.
        """
        if not params_str or not params_str.strip():
            return {}

        # Prepare the string for safe evaluation
        eval_str = params_str.strip()

        # This regex finds unquoted keys (like `pageTitle:`) and adds double quotes.
        eval_str = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', eval_str)

        # Convert JS/JSON booleans and null to Python equivalents
        eval_str = eval_str.replace('true', 'True').replace('false', 'False').replace('null', 'None')

        # Remove trailing commas, which are invalid in literal_eval
        eval_str = re.sub(r',\s*([}\]])', r'\1', eval_str)

        try:
            # ast.literal_eval is much safer than eval() and more flexible than json.loads()
            return ast.literal_eval(eval_str)
        except (ValueError, SyntaxError) as e:
            Log.warning(f"Failed to parse parameters: {params_str[:70]}... Error: {e}")
            return {}

    def _convert_general_includes(self, content: str) -> str:
        """
        Finds all @@include statements, parses their path and parameters,
        and replaces them with a Ruby on Rails <%= render ... %> helper.
        """
        # This single regex handles all cases: with/without params, multiline params
        include_pattern = re.compile(
            r'@@include\(\s*["\']([^"\']+)["\']\s*(?:,\s*(\{[\s\S]*?\}))?\s*\)',
            re.DOTALL
        )

        def replacer(match):
            path_str = match.group(1)
            params_str = match.group(2)  # This will be None if there are no params

            # Clean up the path for the render helper
            # from "./partials/page-title.html" to "partials/page_title"
            render_path = path_str.strip().replace('./', '').replace('.html', '')

            if not params_str:
                return f"<%= render '{render_path}' %>"

            params_dict = self._extract_params_from_include(params_str)
            if not params_dict:
                # If parsing fails, render without params to avoid breaking
                return f"<%= render '{render_path}' %>"

            # Convert the Python dict to a Ruby hash string: {key: "value", ...}
            ruby_params = ", ".join(
                f"{key}: {self._format_ruby_value(value)}"
                for key, value in params_dict.items()
            )

            return f"<%= render '{render_path}', {ruby_params} %>"

        return include_pattern.sub(replacer, content)

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
            return content_div.decode_contents()

        if soup.body:
            return soup.body.decode_contents()

        return original_content_fallback

    def _remove_script_tags(self, content_html):
        soup = BeautifulSoup(content_html, 'html.parser')
        for script in soup.find_all('script'):
            src = script.get('src')
            if src and not src.startswith('http'):
                script.decompose()
        return soup.decode(formatter=None)

    def _extract_vite_scripts(self, soup):
        vite_scripts = []
        for script in soup.find_all('script'):
            src = script.get('src')
            if src and not src.startswith('http'):
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
                Log.created(controller_file_path)

        self._create_routes(controllers_actions)
        Log.info("Controller and routes generation completed")

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

        Log.updated(f"Routes appended to {self.project_routes_path}")

    def _copy_partials(self):
        self.project_partials_path.mkdir(parents=True, exist_ok=True)
        partials_source = self.source_path / "partials"

        if partials_source.exists() and partials_source.is_dir():
            change_extension_and_copy(ROR_EXTENSION, partials_source, self.project_partials_path)

    def _prepare_content_placeholders(self, soup_element):
        """
        Finds all images and relevant links within the soup element,
        replaces their attributes with placeholders, and returns dictionaries
        mapping the placeholders to their final ERB tags.
        """
        link_placeholders = {}
        image_placeholders = {}

        # Prepare Link Placeholders
        link_pattern = re.compile(r'^([a-zA-Z0-9]+)-(.+)\.html$')
        for i, a_tag in enumerate(soup_element.find_all('a', href=True)):
            href = a_tag.get('href')
            if not isinstance(href, str): continue

            match = link_pattern.match(href.strip())
            if match:
                controller = match.group(1)
                action = match.group(2).replace('-', '_')
                erb_tag = f"<%= url_for(:controller => '{controller}', :action => '{action}') %>"
                placeholder = f"__URL_FOR_PLACEHOLDER_{i}__"

                # The key is the full attribute string to be replaced later
                link_placeholders[f'href="{placeholder}"'] = f"href='{erb_tag}'"
                a_tag['href'] = placeholder

        # Prepare Image Placeholders
        for i, img_tag in enumerate(soup_element.find_all('img', src=True)):
            src = img_tag.get('src')
            if not src: continue

            normalized_image_path = None
            if src.startswith(('assets/images/', 'images/')):
                normalized_image_path = src.replace('assets/', '')

            if normalized_image_path:
                safe_path = normalized_image_path.replace("'", "\\'")
                erb_tag = f'<%= vite_asset_path \'{safe_path}\' %>'
                placeholder = f"@@ERB_IMG_PLACEHOLDER_{i}@@"

                # Here the placeholder itself is the key
                image_placeholders[placeholder] = erb_tag
                img_tag['src'] = placeholder  # Modify soup in place

        return link_placeholders, image_placeholders

    def _process_page_file(self, file_path):
        """
        Applies the full conversion process for a main page file, correctly
        extracting the title from various meta-title includes.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 1. Surgically extract the title from various meta-title includes.
        title = "Page Title"  # Default title

        # MODIFIED: This regex now finds any partial include with 'meta-title' or 'title-meta' in its name.
        title_meta_pattern = re.compile(
            r'@@include\(\s*["\']\./partials/([^"\']*?meta-title[^"\']*?|[^"\']*?title-meta[^"\']*?)\.html["\']\s*,\s*(\{[\s\S]*?\})\s*\)',
            re.DOTALL
        )
        match = title_meta_pattern.search(content)
        if match:
            params_str = match.group(2)  # Parameters are now in group 2
            params_dict = self._extract_params_from_include(params_str)

            # MODIFIED: Check for 'pageTitle' as well as 'title'.
            if 'title' in params_dict:
                title = params_dict['title']
            elif 'pageTitle' in params_dict:
                title = params_dict['pageTitle']

            # Remove the include so it's not processed again
            content = title_meta_pattern.sub('', content, count=1)

        erb_header = f"<% @title = \"{title}\" %>\n\n"

        # 2. Perform all other conversions on the remaining content
        content = self._convert_general_includes(content)
        soup = BeautifulSoup(content, 'html.parser')

        # 3. Read info and modify the soup object
        vite_scripts = self._extract_vite_scripts(soup)
        main_content_element = self._extract_main_content(soup, content)
        if isinstance(main_content_element, str):
            main_content_element = BeautifulSoup(main_content_element, 'html.parser')

        link_placeholders, image_placeholders = self._prepare_content_placeholders(main_content_element)

        for script in main_content_element.find_all('script'):
            src = script.get('src')
            if src and not src.startswith('http'):
                script.decompose()

        # 4. Serialize the modified soup back to a string
        content_with_placeholders = main_content_element.decode(formatter=None)

        # 5. Perform all ERB replacements on the clean string
        final_content = content_with_placeholders
        for placeholder_attr, final_attr in link_placeholders.items():
            final_content = final_content.replace(placeholder_attr, final_attr)
        for placeholder, erb_tag in image_placeholders.items():
            final_content = final_content.replace(f'src="{placeholder}"', f'src="{erb_tag}"')

        # 6. Assemble the final file content
        erb_output = (
                erb_header +
                final_content.strip() +
                "\n\n<% content_for :javascript do %>\n"
        )
        for script in vite_scripts:
            erb_output += f"  <%= vite_javascript_tag '{script}' %>\n"
        erb_output += "<% end %>\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(erb_output)
        Log.converted(str(file_path))

    def _process_partial_file(self, file_path):
        """
        Applies a lightweight conversion process for a partial file, following the
        "Parse Once" rule.
        """
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Perform initial text-only substitutions
        content = self._convert_general_includes(content)

        # Parse the HTML ONCE.
        soup = BeautifulSoup(content, 'html.parser')

        # Read info and modify the soup object
        vite_scripts = self._extract_vite_scripts(soup)
        link_placeholders, image_placeholders = self._prepare_content_placeholders(soup)

        # Safely remove script tags from the soup object
        for script in soup.find_all('script'):
            src = script.get('src')
            if src and not src.startswith('http'):
                script.decompose()

        # Serialize the modified soup back to a string
        content_with_placeholders = soup.decode(formatter=None)

        # Perform all ERB replacements on the clean string
        final_content = content_with_placeholders
        for placeholder_attr, final_attr in link_placeholders.items():
            final_content = final_content.replace(placeholder_attr, final_attr)
        for placeholder, erb_tag in image_placeholders.items():
            final_content = final_content.replace(f'src="{placeholder}"', f'src="{erb_tag}"')

        # Assemble the final file content
        if vite_scripts:
            script_block = "\n"
            for script in vite_scripts:
                script_block += f"\n<%= vite_javascript_tag '{script}' %>"
            final_content += script_block

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(final_content.strip())

        Log.converted(str(file_path))

    def _replace_partial_variables(self):
        """
        Replace @@<var> with short echo '<?= $<var> ?>' across all PHP files.
        Skips control/directive tokens like @@if and @@include.
        """
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_partials_path.rglob(f"*{ROR_EXTENSION}"):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            new_content = pattern.sub(r'<%= \1 %>', content)
            if new_content != content:
                file.write_text(new_content, encoding="utf-8")
                Log.updated(str(file))
                count += 1

        if count:
            Log.info(f"{count} files updated in {self.project_partials_path}")
