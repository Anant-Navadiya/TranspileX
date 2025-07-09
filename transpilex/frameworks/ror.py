import json
import re
from pathlib import Path
from bs4 import BeautifulSoup

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

        # Ensure the views path exists for output
        self.project_views_path.mkdir(parents=True, exist_ok=True)

        self.create_project()  # Call this explicitly if needed for full workflow

    def create_project(self):
        """
        Initializes the project structure and restructures files.
        """
        Messenger.info(f"Creating project structure for '{self.project_name}'...")
        empty_folder_contents(self.project_views_path)
        restructure_files(self.source_path, self.project_views_path, new_extension=ROR_EXTENSION,
                          skip_dirs=['partials'], keep_underscore=True)
        Messenger.info("Project structure created.")
        self._convert()

    def _convert(self):
        """
        Converts HTML files with custom @@include statements into Ruby on Rails ERB views.
        """
        count = 0

        # Iterate through all .html.erb files in the project views path
        for file in self.project_views_path.rglob(f"*.html.erb"):
            Messenger.info(f"Processing file: {file.relative_to(self.project_views_path)}")
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            original_content = content  # Keep a copy of the original content
            soup_original = BeautifulSoup(original_content, 'html.parser')

            # --- Step 1: Extract and remove page-title include ---
            page_title_render_string = ""
            page_title_include_params = {}
            title_from_page_title_include = None

            # Pattern to find @@include for page-title.html and capture its parameters
            page_title_pattern = r'(@@include\(\s*["\']\.?\/partials\/page-title\.html["\']\s*,\s*(array\(.*?\)|\{.*?\})\s*\))'
            page_title_match = re.search(page_title_pattern, original_content, flags=re.DOTALL)

            if page_title_match:
                full_include_string = page_title_match.group(1)  # The entire @@include(...) string
                params_str = page_title_match.group(2)  # Just the parameters part (e.g., {"title": "Calendar"})

                page_title_include_params = self._extract_params_from_include(params_str)

                # Construct the Rails render string using all extracted parameters
                if page_title_include_params:
                    def ruby_value(v):
                        """Converts Python value to Ruby string representation."""
                        if isinstance(v, str):
                            # Escape backslashes and double quotes for Ruby string literal
                            escaped = v.replace('\\', '\\\\\\\\').replace('"', '\\"')
                            return f'"{escaped}"'
                        elif isinstance(v, bool):
                            return 'true' if v else 'false'
                        elif v is None:
                            return 'nil'
                        else:
                            return str(v)

                    # Join parameters into a Ruby hash string (e.g., title: "Calendar, sub_title: "Apps")
                    params_str_ruby = ", ".join(f"{k}: {ruby_value(v)}" for k, v in page_title_include_params.items())
                    page_title_render_string = f"<%= render 'layouts/partials/page_title', {params_str_ruby} %>\n\n"

                    # Extract the 'title' specifically for the @title ERB variable
                    if "title" in page_title_include_params:
                        title_from_page_title_include = page_title_include_params["title"]

                # Remove the original @@include statement from the content
                content = content.replace(full_include_string, "")
                Messenger.info(f"Removed page-title include: {full_include_string[:50]}...")

            # --- Step 2: Determine the main page title for @title ERB variable ---
            title = title_from_page_title_include
            if not title:  # If title wasn't found in page-title include, try <title> tag or data-title attribute
                title = self._extract_title_from_soup_or_data(soup_original) or "Page Title"
            Messenger.info(f"Determined page title: '{title}'")

            # --- Step 3: Prepare Rails ERB header with page title instance variable ---
            erb_header = f"<% @title = \"{title}\" %>\n\n"

            # --- Step 4: Convert all other @@include statements (excluding page-title.html) ---
            # This operates on the 'content' which now has the page-title include removed
            content = self.convert_general_includes(content)
            Messenger.info("Converted general includes.")

            # --- Step 5: Extract main content (after general includes conversion) ---
            # Re-parse the content into a new BeautifulSoup object to reflect changes
            soup_current = BeautifulSoup(content, 'html.parser')
            main_content = self._extract_main_content(soup_current, content)
            Messenger.info("Extracted main content.")

            # --- Step 5.5: Convert image paths ---
            main_content = self._convert_image_paths(main_content)
            Messenger.info("Converted image paths in main content.")

            # --- Step 6: Extract script tags from original content ---
            # We extract from the original soup to ensure all script tags are captured
            vite_scripts = self._extract_vite_scripts(soup_original)
            Messenger.info(f"Extracted {len(vite_scripts)} script tags.")

            # --- Step 7: Remove script tags from main content ---
            main_content = self._remove_script_tags(main_content)
            Messenger.info("Removed script tags from main content.")

            # --- Step 8: Compose final ERB output ---
            erb_output = (
                    erb_header +  # <% @title = "..." %>
                    page_title_render_string +  # <%= render 'layouts/partials/page_title', ... %> (if present)
                    main_content.strip() +  # The cleaned HTML content
                    "\n\n<% content_for :javascript do %>\n"  # Start of JS block
            )

            # Add vite_javascript_tag calls for each extracted script
            for script in vite_scripts:
                erb_output += f"  <%= vite_javascript_tag '{script}' %>\n"
            erb_output += "<% end %>\n"  # End of JS block

            # --- Step 9: Removed: Clean relative asset paths (handled by specific converters) ---
            # The path normalization is now handled within _convert_image_paths and _extract_vite_scripts.
            # Applying clean_relative_asset_paths to the final ERB output could corrupt helper strings.
            # erb_output = clean_relative_asset_paths(erb_output)
            # Messenger.info("Cleaned asset paths.") # This message is now redundant

            # Write the converted content back to the file
            with open(file, "w", encoding="utf-8") as f:
                f.write(erb_output)

            Messenger.success(f"Converted Rails view: {file.relative_to(self.project_views_path)}")
            count += 1

        Messenger.success(f"\n{count} Rails view files converted successfully.")

    def convert_general_includes(self, content):
        """
        Converts all @@include(...) statements in the content, excluding page-title.html,
        into simple Rails render calls.
        """
        # Pattern to match all @@include except page-title.html
        # It also allows for optional parameters, though they are ignored for general includes
        pattern_general = r'@@include\(\s*["\']\.?\/partials\/(?!page-title\.html)([^"\']+)["\'](?:\s*,\s*(array\(.*?\)|\{.*?\}))?\s*\)'

        def general_replacer(m):
            partial_name = m.group(1).replace('.html', '')  # Get partial name without .html extension
            # For general includes, we convert to a simple Rails render call without parameters
            return f"<%= render 'layouts/partials/{partial_name}' %>"

        # Substitute all matches with the Rails render syntax
        content = re.sub(pattern_general, general_replacer, content, flags=re.DOTALL)
        return content

    def _extract_params_from_include(self, params_str):
        """
        Extracts parameters from a string containing either JSON or PHP array syntax.
        Returns a dictionary of parameters.
        """
        # Try JSON parsing first
        try:
            # Replace single quotes with double quotes for JSON parsing compatibility
            json_str_cleaned = params_str.replace("'", '"')
            # Use a regex to quote unquoted keys if they exist (e.g., {key: "value"})
            # This regex matches a starting brace or comma, followed by optional whitespace,
            # then an unquoted word (key), then optional whitespace and a colon.
            # It replaces it with the same, but with the key wrapped in double quotes.
            json_str_cleaned = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str_cleaned)
            return json.loads(json_str_cleaned)
        except json.JSONDecodeError:
            Messenger.warning(f"Failed to parse as JSON: {params_str[:50]}...")
            pass  # Fallback to PHP array parsing if JSON fails

        # Try PHP array parsing if JSON parsing failed
        params_dict = {}
        # This regex is designed to parse key-value pairs from PHP array syntax.
        # It handles keys (quoted or unquoted), and values (strings, numbers, booleans, null).
        param_pattern = re.compile(r"""
            (?:['"]?(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)['"]?\s*=>\s*)?   # Key (optional, handles 'key' => or key =>)
            (?:
                ['"](?P<sval>(?:\\.|[^'"])*)['"]  # String value (handles escaped quotes like \" or \')
                |
                (?P<nval>-?\d+(?:\.\d+)?)         # Numeric value (int or float)
                |
                (?P<bool>true|false)               # Boolean value
                |
                (?P<null>null)                     # Null value
            )
            \s*(?:,\s*|$) # Separator (comma and optional whitespace) or end of string
        """, re.VERBOSE | re.DOTALL)

        for match in param_pattern.finditer(params_str):
            key = match.group('key')
            # If a key is not explicitly found (e.g., for simple arrays without explicit keys), skip.
            # Our current use case expects key-value pairs.
            if not key:
                continue

            if match.group('sval') is not None:
                # Unescape quotes within string values
                value = match.group('sval').replace('\\"', '"').replace("\\'", "'")
            elif match.group('nval') is not None:
                # Convert numeric string to int or float
                value = float(match.group('nval')) if '.' in match.group('nval') else int(match.group('nval'))
            elif match.group('bool') is not None:
                # Convert boolean string to Python boolean
                value = True if match.group('bool') == 'true' else False
            elif match.group('null') is not None:
                value = None
            else:
                value = None  # Should ideally not be reached if regex is comprehensive

            params_dict[key] = value

        if not params_dict:
            Messenger.warning(f"Could not extract parameters from: {params_str[:50]}...")
        return params_dict

    def _extract_title_from_soup_or_data(self, soup):
        """
        Extracts the page title from a <title> tag or a data-title attribute.
        This is used as a fallback if the title is not found in a page-title include.
        """
        if soup.title and soup.title.string:
            return soup.title.string.strip()

        data_title_elem = soup.find(attrs={"data-title": True})
        if data_title_elem:
            return data_title_elem["data-title"].strip()

        return None

    def _extract_main_content(self, soup, original_content_fallback):
        """
        Extracts the main content of the HTML.
        Prioritizes a div with data-content attribute, then the body contents,
        otherwise returns the whole original content as a fallback.
        """
        content_div = soup.find(attrs={"data-content": True})
        if content_div:
            # Return the string representation of all children within the data-content div
            return ''.join(str(c) for c in content_div.contents)

        if soup.body:
            # Return the string representation of all children within the body tag
            return ''.join(str(c) for c in soup.body.contents)

        return original_content_fallback

    def _remove_script_tags(self, content_html):
        """
        Removes all <script> tags from the given HTML content.
        """
        soup = BeautifulSoup(content_html, 'html.parser')
        for script in soup.find_all('script'):
            script.decompose()  # Remove the script tag from the soup
        return str(soup)  # Return the modified soup as a string

    def _convert_image_paths(self, content_html):
        """
        Converts image src attributes to Rails vite_asset_path helper calls.
        Assumes paths like 'assets/images/...' or 'images/...'.
        Uses placeholders to prevent BeautifulSoup from escaping ERB tags.
        """
        # Define placeholders for characters that BeautifulSoup might escape
        PLACEHOLDER_LT = "__BS4_LT__"
        PLACEHOLDER_GT = "__BS4_GT__"
        PLACEHOLDER_QUOTE = "__BS4_QUOTE__"  # For single quote within the ERB string

        soup = BeautifulSoup(content_html, 'html.parser')
        for img_tag in soup.find_all('img'):
            src = img_tag.get('src')
            if src:
                normalized_image_path = None
                if src.startswith('assets/images/'):
                    normalized_image_path = src.replace('assets/', '')
                elif src.startswith('images/'):
                    normalized_image_path = src

                if normalized_image_path:
                    # Construct the ERB tag with placeholders
                    # Note the space after 'vite_asset_path' and single quotes around the path
                    erb_src_with_placeholders = (
                        f"{PLACEHOLDER_LT}%= vite_asset_path {PLACEHOLDER_QUOTE}{normalized_image_path}{PLACEHOLDER_QUOTE} %{PLACEHOLDER_GT}"
                    )
                    img_tag['src'] = erb_src_with_placeholders
                    Messenger.info(f"Converted image src: {src} -> {erb_src_with_placeholders}")

        modified_html_string = str(soup)

        # Replace placeholders back with actual characters
        modified_html_string = modified_html_string.replace(PLACEHOLDER_LT, '<')
        modified_html_string = modified_html_string.replace(PLACEHOLDER_GT, '>')
        modified_html_string = modified_html_string.replace(PLACEHOLDER_QUOTE, "'")

        return modified_html_string

    def _extract_vite_scripts(self, soup):
        """
        Extracts source paths from <script> tags for conversion to vite_javascript_tag.
        """
        vite_scripts = []
        for script in soup.find_all('script'):
            src = script.get('src')
            if not src:
                continue
            # Normalize path: remove leading '/' and 'assets/' prefix if present
            normalized_src = src.lstrip('/').replace('assets/', '')
            vite_scripts.append(normalized_src)
        return vite_scripts
