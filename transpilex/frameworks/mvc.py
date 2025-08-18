import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.config.base import MVC_DESTINATION_FOLDER, MVC_ASSETS_FOLDER, MVC_PROJECT_CREATION_COMMAND, \
    SLN_FILE_CREATION_COMMAND, MVC_GULP_ASSETS_PATH, MVC_EXTENSION
from transpilex.helpers import copy_assets
from transpilex.helpers.plugins_file import plugins_file
from transpilex.helpers.casing import to_pascal_case
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.empty_folder_contents import empty_folder_contents
from transpilex.helpers.gulpfile import add_gulpfile
from transpilex.helpers.logs import Log
from transpilex.helpers.restructure_files import apply_casing
from transpilex.helpers.package_json import update_package_json
from transpilex.helpers.validations import folder_exists


class MVCConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True):
        self.project_name = project_name.title()
        self.source_path = Path(source_path)
        self.destination_path = Path(MVC_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp

        self.project_root = self.destination_path / self.project_name
        self.project_assets_path = self.project_root / MVC_ASSETS_FOLDER
        self.project_views_path = self.project_root / "Views"
        self.project_partials_path = self.project_views_path / "Shared" / "Partials"
        self.project_controllers_path = Path(self.project_root / "Controllers")

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        self.project_root.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                f'{MVC_PROJECT_CREATION_COMMAND} {self.project_name}', cwd=self.project_root.parent,
                shell=True, check=True)

            Log.success("MVC project created successfully")

            subprocess.run(
                f'{SLN_FILE_CREATION_COMMAND} {self.project_name}', cwd=self.project_root.parent, shell=True,
                check=True)

            sln_file = f"{self.project_name}.sln"

            subprocess.run(
                f'dotnet sln {sln_file} add {Path(self.project_name) / self.project_name}.csproj',
                cwd=self.project_root.parent, shell=True, check=True)

            Log.info(".sln file created successfully")


        except subprocess.CalledProcessError:
            Log.error("MVC project creation failed")
            return

        empty_folder_contents(self.project_views_path, skip=['_ViewStart.cshtml', '_ViewImports.cshtml'])

        self._copy_partials()

        self._convert(skip_dirs=['partials'])

        self._replace_partial_variables()

        self._create_controllers(ignore_list=['Shared'])

        copy_assets(self.assets_path, self.project_assets_path)

        if self.include_gulp:
            has_plugins_file = plugins_file(self.source_path, self.project_root)
            add_gulpfile(self.project_root, MVC_GULP_ASSETS_PATH, has_plugins_file)
            update_package_json(self.source_path, self.project_root, self.project_name)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self, skip_dirs=None, casing="pascal"):
        count = 0
        if skip_dirs is None:
            skip_dirs = ['partials']

        # Define which partials are allowed to set the page's ViewBag properties
        page_title_partials = ["page-title.html", "app-pagetitle.html", "title-meta.html", "app-meta-title.html"]

        for file in self.source_path.rglob("*.html"):
            relative_file_path_str = str(file.relative_to(self.source_path)).replace("\\", "/")
            if not file.is_file() or any(skip in relative_file_path_str for skip in skip_dirs):
                continue

            with open(file, "r", encoding="utf-8") as f:
                raw_html = f.read()

            # Process all includes and extract page-title data at the same time
            processed_html, viewbag_data = self._process_includes(raw_html, page_title_partials)

            if not viewbag_data:
                Log.warning(
                    f"No ViewBag data extracted for page: {file.name}")

            soup = BeautifulSoup(processed_html, "html.parser")

            # ... (the rest of your logic for finding scripts, links, and content block) ...
            all_script_tags = soup.find_all('script')
            link_tags = soup.find_all('link', rel='stylesheet')

            scripts_to_move = []
            # Define the exact text of the script you want to exclude
            script_to_exclude = "document.write(new Date().getFullYear())"

            for tag in all_script_tags:
                # Check if the tag's text content matches the one to exclude
                if tag.get_text(strip=True) == script_to_exclude:
                    # If it matches, do nothing. Leave it in the main content.
                    pass
                else:
                    # For ALL other scripts (inline or external), add them to the move list.
                    scripts_to_move.append(tag)

            scripts_content = "\n    ".join([str(tag) for tag in scripts_to_move])
            styles_content = "\n    ".join([str(tag) for tag in link_tags])

            # Decompose only the tags that have been moved.
            tags_to_decompose = scripts_to_move + link_tags
            for tag in tags_to_decompose:
                tag.decompose()

            content_block = soup.find(attrs={"data-content": True})
            if content_block:
                main_content = content_block.decode_contents().strip()
            elif soup.body:
                main_content = soup.body.decode_contents().strip()
            else:
                main_content = soup.decode_contents().strip()

            # ... (the rest of your logic for determining file names and paths) ...
            base_name = file.stem
            if '-' in base_name:
                name_parts = [part.replace("_", "-") for part in base_name.split('-')]
                final_file_name = name_parts[-1]
                file_based_folders = name_parts[:-1]
            else:
                file_based_folders = [base_name.replace("_", "-")]
                final_file_name = "index"

            relative_path = file.relative_to(self.source_path)
            relative_folder_parts = list(relative_path.parent.parts)
            combined_folder_parts = relative_folder_parts + file_based_folders
            processed_folder_parts = [apply_casing(p, casing) for p in combined_folder_parts]
            processed_file_name = apply_casing(final_file_name, casing)

            target_dir = self.project_views_path / Path(*processed_folder_parts)
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / f"{processed_file_name}{MVC_EXTENSION}"
            route_path = "/" + base_name.lower().replace("_", "-")

            # Generate ViewBag code from the extracted data
            if not viewbag_data.get("Title"):
                viewbag_data["Title"] = processed_file_name  # Fallback title

            viewbag_code = self._generate_viewbag_code(viewbag_data)

            # ... (your logic for generating the final cshtml_content string) ...
            cshtml_content = f"""{viewbag_code}

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
            cshtml_content = self._replace_html_links(cshtml_content, current_source_dir=file.parent)

            with open(target_file, "w", encoding="utf-8") as f:
                f.write(cshtml_content.strip() + "\n")

            Log.converted(str(target_file))
            count += 1

        Log.info(f"{count} files converted in {self.project_views_path}")

    def _process_includes(self, content: str, page_title_partials: list[str]):
        """
        Processes all @@include directives in a given string.
        ...
        """
        viewbag_data = {}

        pattern = re.compile(r'@@include\(\s*["\'](.*?)["\']\s*(?:,\s*({.*?}))?\s*\)', re.DOTALL)

        def replacer(match):
            partial_path_str = match.group(1)
            json_str = match.group(2)

            partial_path = Path(partial_path_str)
            partial_filename = partial_path.name
            partial_stem = partial_path.stem

            if partial_filename in page_title_partials and json_str:
                try:
                    # ---> ADDED QUOTE NORMALIZATION LINE <---
                    # Convert all single quotes to double quotes to handle both styles
                    normalized_json = json_str.replace("'", '"')

                    # This regex finds all "key": "value" pairs, ignoring formatting issues.
                    kv_pattern = re.compile(r'"([^"]+)"\s*:\s*"([^"]*)"')
                    matches = kv_pattern.findall(normalized_json)

                    if not matches:
                        Log.warning(f"Could not extract any key-value pairs from {partial_filename}")

                    # Add all found pairs to the viewbag_data dictionary
                    for key, value in matches:
                        viewbag_data[to_pascal_case(key)] = value.strip()

                except Exception as e:
                    # A general catch-all just in case of unexpected errors
                    Log.error(f"An unexpected error occurred while parsing JSON for {partial_filename}. Reason: {e}")
                    Log.info(f"Problematic string: {json_str}")

            # Convert the partial's filename to the Razor convention (_PascalCase.cshtml)
            pascal_stem = to_pascal_case(partial_stem)
            razor_partial_name = f"_{pascal_stem}{MVC_EXTENSION}"

            # Return the Razor syntax for a partial view
            return f'@await Html.PartialAsync("~/Views/Shared/Partials/{razor_partial_name}")'

        processed_content = pattern.sub(replacer, content)
        return processed_content, viewbag_data

    def _generate_viewbag_code(self, data: dict):
        if not data:
            return ""

        lines = []
        for key, val in data.items():
            val_str = str(val).replace('"', '\\"')
            lines.append(f'ViewBag.{key} = "{val_str}";')

        return "@{\n    " + "\n    ".join(lines) + "\n}"

    def _create_controller_file(self, path, controller_name, actions):
        """Creates a controller file with basic action methods."""
        using_statements = "using Microsoft.AspNetCore.Mvc;"

        controller_class = f"""
namespace {self.project_name}.Controllers
{{
    public class {controller_name}Controller : Controller
    {{
{"".join([f"""        public IActionResult {action}()
        {{
            return View();
        }}\n\n""" for action in actions])}    }}
}}
    """.strip()

        with open(path, "w", encoding="utf-8") as f:
            f.write(using_statements + "\n\n" + controller_class)

    def _create_controllers(self, ignore_list=None):
        """
        Generates controller files based on folders and .cshtml files in the views folder.
        Deletes existing Controllers folder and recreates it.

        :param ignore_list: List of folder or file names to ignore
        """
        ignore_list = ignore_list or []

        if os.path.isdir(self.project_controllers_path):
            Log.info(f"Removing existing Controllers folder: {self.project_controllers_path}")
            shutil.rmtree(self.project_controllers_path)

        os.makedirs(self.project_controllers_path, exist_ok=True)

        for folder_name in os.listdir(self.project_views_path):
            if folder_name in ignore_list:
                continue

            folder_path = os.path.join(self.project_views_path, folder_name)
            if not os.path.isdir(folder_path):
                continue

            actions = []
            for file in os.listdir(folder_path):
                if file in ignore_list:
                    continue
                if file.endswith(".cshtml") and not file.endswith(".cshtml.cs") and not file.startswith("_"):
                    action_name = os.path.splitext(file)[0]
                    actions.append(action_name)

            if actions:
                controller_file_path = os.path.join(self.project_controllers_path, f"{folder_name}Controller.cs")
                self._create_controller_file(controller_file_path, folder_name, actions)
                Log.created(controller_file_path)

        Log.info(f"Controller generation completed")

    def _copy_partials(self):
        """
        Copies and processes partials from the source folder.
        It renames them to _PascalCase.cshtml, and processes their content
        for nested includes.
        """
        self.project_partials_path.mkdir(parents=True, exist_ok=True)
        partials_source = self.source_path / "partials"

        if partials_source.exists() and partials_source.is_dir():
            for filename in os.listdir(partials_source):
                source_file = partials_source / filename
                if not source_file.is_file():
                    continue

                # Read the original partial's content
                with open(source_file, "r", encoding="utf-8") as f:
                    content = f.read()

                # Process its content for nested includes.
                # We pass an empty list because partials should not set the page's ViewBag.
                processed_content, _ = self._process_includes(content, [])

                # Also clean asset paths within the partial
                processed_content = clean_relative_asset_paths(processed_content)
                processed_content = self._replace_html_links(processed_content, current_source_dir=source_file.parent)

                # Determine the new _PascalCase.cshtml filename
                pascal_stem = to_pascal_case(source_file.stem)
                new_filename = f"_{pascal_stem}{MVC_EXTENSION}"
                destination_file = self.project_partials_path / new_filename

                # Write the processed content to the new file
                with open(destination_file, "w", encoding="utf-8") as f:
                    f.write(processed_content)

    def _replace_partial_variables(self):
        """
        Replace @@<var> with short echo '<?= $<var> ?>' across all PHP files.
        Skips control/directive tokens like @@if and @@include.
        """
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_partials_path.rglob(f"*{MVC_EXTENSION}"):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            new_content = pattern.sub(r'@\1', content)
            if new_content != content:
                file.write_text(new_content, encoding="utf-8")
                Log.updated(str(file))
                count += 1

        if count:
            Log.info(f"{count} files updated in {self.project_partials_path}")

    def _generate_candidates(self, parent, fname):
        """Generate normalized variants of a filename with -/_ permutations"""
        stem, ext = Path(fname).stem, Path(fname).suffix
        # Split on both - and _
        parts = re.split(r'[-_]+', stem)

        variants = set()

        # 1. Keep original
        variants.add(stem)

        # 2. All hyphens
        variants.add("-".join(parts))
        # 3. All underscores
        variants.add("_".join(parts))
        # 4. Mixed: hyphen→underscore and underscore→hyphen replacements
        variants.add(stem.replace('-', '_'))
        variants.add(stem.replace('_', '-'))

        return [parent / (v + ext) for v in variants]

    def _tokenize(self, stem: str) -> tuple[str, ...]:
        # split on both '-' and '_', lowercase for stable compare
        return tuple(t for t in re.split(r'[-_]+', stem.lower()) if t)

    def _build_file_index(self):
        """Cache a list of (path, stem, tokens) for all *.html under source_path."""
        if hasattr(self, "_file_index"):
            return
        self._file_index = []
        for f in self.source_path.rglob("*.html"):
            if f.is_file():
                stem = f.stem
                toks = self._tokenize(stem)
                self._file_index.append((f, stem, toks))

    def _find_matching_file_strict(self, href_name: str, preferred_dir: Path | None = None) -> Path | None:
        """
        Strict resolver:
        - tokens(link) must equal tokens(file)
        - no suffix/prefix allowances
        - break ties by preferring same directory (if provided)
        """
        self._build_file_index()
        link_stem = Path(href_name).stem
        link_tokens = self._tokenize(link_stem)
        if not link_tokens:
            return None

        candidates = [(p, stem, toks) for (p, stem, toks) in self._file_index if toks == link_tokens]
        if not candidates:
            return None

        if preferred_dir is not None:
            same_dir = [p for (p, _, _) in candidates if p.parent.resolve() == preferred_dir.resolve()]
            if same_dir:
                return same_dir[0]

        # otherwise just return the first exact-token match
        return candidates[0][0]

    def _replace_html_links(self, content: str, current_source_dir=None) -> str:
        """
        Replace static .html links with Razor @Url.Action(...) according to:
          - '-' = folder/segment separator (Area / Controller / Action)
          - '_' = single word within a segment
        Strict filename matching by tokens (split on '-' and '_'):
          - 'auth-sign-in.html' == 'auth-sign_in.html'   ✅
          - 'calendar.html'     != 'apps-calendar.html'  ❌
        Also emits href without quotes: href=@Url.Action("Action","Controller")
        """
        soup = BeautifulSoup(content, "html.parser")

        for link in soup.find_all("a", href=True):
            href = link.get("href")
            if (not href or
                    not href.endswith(".html") or
                    href.startswith(("#", "javascript:", "http"))):
                continue

            clean_href = href.strip().lstrip('/')
            fname = Path(clean_href).name  # match by filename only

            matched_path = self._find_matching_file_strict(fname, preferred_dir=current_source_dir)
            if not matched_path:
                Log.warning(f"Skipping link conversion for '{href}'. Source file not found.")
                continue

            matched_base = matched_path.stem  # e.g., "maps-leaflet" or "auth-sign_in"

            # '-' define segments (Area / Controller / Action). Keep '_' inside segments.
            segments = [s for s in matched_base.split('-') if s]
            n = len(segments)

            def P(seg: str) -> str:
                # your _to_pascal_case already splits underscores/camelCase -> PascalCase
                return to_pascal_case(seg)

            if n == 1:
                controller, action = P(segments[0]), "Index"
                razor = f'@Url.Action("{action}", "{controller}")'
            elif n == 2:
                controller, action = P(segments[0]), P(segments[1])
                razor = f'@Url.Action("{action}", "{controller}")'
            else:
                area, controller, action = P(segments[0]), P(segments[-2]), P(segments[-1])
                razor = f'@Url.Action("{action}", "{controller}", new {{ area = "{area}" }})'

            # set attribute (BeautifulSoup will quote it; we strip quotes later)
            link["href"] = razor

        html = str(soup)

        # Strip quotes only when href starts with @Url.Action(...)
        # Handle both single- and double-quoted cases safely.
        html = re.sub(r'href=\'(@Url\.Action\([^\']*\))\'', r'href=\1', html)
        html = re.sub(r'href="(@Url\.Action\([^"]*\))"', r'href=\1', html)

        return html
