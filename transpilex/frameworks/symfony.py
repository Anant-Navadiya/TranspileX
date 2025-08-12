import re
import ast
import subprocess
import html
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.config.base import SYMFONY_DESTINATION_FOLDER, SYMFONY_INSTALLATION_VERSION, SYMFONY_ASSETS_FOLDER, \
    SYMFONY_ASSETS_PRESERVE, SYMFONY_EXTENSION, SYMFONY_GULP_ASSETS_PATH
from transpilex.helpers import copy_assets, change_extension_and_copy
from transpilex.helpers.add_plugins_file import add_plugins_file
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.add_gulpfile import add_gulpfile
from transpilex.helpers.logs import Log
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.package_json import update_package_json


class SymfonyConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str, include_gulp: bool = True):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(SYMFONY_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)
        self.include_gulp = include_gulp

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / SYMFONY_ASSETS_FOLDER
        self.project_pages_path = Path(self.project_root / "templates")
        self.project_partials_path = Path(self.project_pages_path / "partials")
        self.project_controller_path = Path(self.project_root / "src" / "Controller")
        self.project_home_controller_path = Path(self.project_controller_path / "HomeController.php")

        self.create_project()

    def create_project(self):

        Log.project_start(self.project_name)

        self.project_root.parent.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(f'symfony new {self.project_root} --version="{SYMFONY_INSTALLATION_VERSION}" --webapp',
                           shell=True,
                           check=True)
            Log.success(f"Symfony project created successfully")

        except subprocess.CalledProcessError:
            Log.error(f"Symfony project creation failed")
            return

        change_extension_and_copy(SYMFONY_EXTENSION, self.source_path, self.project_pages_path)

        self._convert(self.project_pages_path)

        self._replace_partial_variables()

        self._add_home_controller()

        copy_assets(self.assets_path, self.project_assets_path, preserve=SYMFONY_ASSETS_PRESERVE)

        if self.include_gulp:
            add_gulpfile(self.project_root, SYMFONY_GULP_ASSETS_PATH)
            add_plugins_file(self.source_path, self.project_root)
            update_package_json(self.source_path, self.project_root, self.project_name)

        Log.project_end(self.project_name, str(self.project_root))

    def _process_includes(self, content: str):
        twig_title_block = ""

        def replacer_with_params(match):
            nonlocal twig_title_block

            file_partial_path = match.group(1).strip()
            params_str = match.group(2).strip()

            # Collapse whitespace INSIDE quoted strings only (so multi-line values are safe)
            def _collapse_in_strings(m):
                q = m.group(1)
                inner = m.group(2)
                inner = re.sub(r'\s+', ' ', inner).strip()
                return q + inner + q

            string_lit_rx = r'''(["'])((?:(?!\1|\\).|\\.)*)\1'''
            params_str = re.sub(string_lit_rx, _collapse_in_strings, params_str, flags=re.DOTALL)

            # Remove trailing commas like {"a":"b",}
            params_str_cleaned = re.sub(r',\s*(?=[}\]])', '', params_str)

            # Try a tolerant parse
            try:
                params_dict = ast.literal_eval(params_str_cleaned)
            except (ValueError, SyntaxError) as e:
                Log.error(f"Could not parse params for '{file_partial_path}'. Error: {e}")
                return match.group(0)

            # Title/meta includes: lift title into a Twig block and drop the include
            name_lower = Path(file_partial_path).name.lower()
            if name_lower in ("title-meta.html", "app-meta-title.html"):
                title = (params_dict.get("title") or params_dict.get("pageTitle") or "").strip()
                if title:
                    title = html.unescape(title)
                    twig_title_block = f"{{% block title %}}{title}{{% endblock %}}"
                return ""

            # Build Twig params: key: value (strings single-quoted, booleans true/false)
            def _twig_value(v):
                if isinstance(v, str):
                    s = html.unescape(v).replace("'", "\\'")
                    return f"'{s}'"
                if isinstance(v, bool):
                    return "true" if v else "false"
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    return str(v)
                # fallback stringify
                s = str(v).replace("'", "\\'")
                return f"'{s}'"

            twig_params = ", ".join(f"{k}: {_twig_value(v)}" for k, v in params_dict.items())

            # Keep original filename (e.g. page-title.html) and append .twig
            view_name = Path(file_partial_path).name + ".twig"
            return f"{{{{ include('partials/{view_name}', {{ {twig_params} }}) }}}}"

        def replacer_no_params(match):
            file_partial_path = match.group(1).strip()
            # Drop footer includes entirely
            name_lower = Path(file_partial_path).name.lower()
            if name_lower in ("footer.html", "footer-scripts.html"):
                return ""
            view_name = Path(file_partial_path).name + ".twig"
            return f"{{{{ include('partials/{view_name}') }}}}"

        include_with_params_regex = r"""@@include\s*\(\s*['"]([^"']+)['"]\s*,\s*(\{[\s\S]*?\})\s*\)"""
        processed_content = re.sub(include_with_params_regex, replacer_with_params, content, flags=re.DOTALL)

        include_no_params_regex = r"""@@include\s*\(\s*['"]([^"']+)['"]\s*\)"""
        processed_content = re.sub(include_no_params_regex, replacer_no_params, processed_content)

        return processed_content, twig_title_block.strip()

    def _convert(self, dist_folder):
        dist_path = Path(dist_folder)
        count = 0

        for file in dist_path.rglob("*.html.twig"):
            if not file.is_file():
                continue

            content = file.read_text(encoding="utf-8")

            is_partial = 'partials' in str(file.relative_to(dist_path))

            if is_partial:
                # For partials, just process includes and clean paths. No layout.
                processed_content, _ = self._process_includes(content)  # Discard title block
                processed_content = clean_relative_asset_paths(processed_content)
                processed_content = replace_html_links(processed_content, '')

                file.write_text(processed_content.strip() + "\n", encoding="utf-8")
                Log.converted(f"{str(file.relative_to(self.project_pages_path))} (processed as partial)")
                count += 1

            else:
                # For main pages, perform the full conversion with the layout.
                processed_content, twig_title_block = self._process_includes(content)
                soup = BeautifulSoup(processed_content, 'html.parser')

                link_tags = soup.find_all("link", rel="style")
                styles_html = "\n".join(f"    {tag.extract()}" for tag in link_tags)

                script_tags = soup.find_all("script")
                scripts_html = "\n".join(f"    {tag.extract()}" for tag in script_tags)

                content_div = soup.find(attrs={"data-content": True})
                if content_div:
                    content_section = content_div.decode_contents().strip()
                else:
                    body_tag = soup.find("body")
                    content_section = body_tag.decode_contents().strip() if body_tag else soup.decode_contents().strip()

                twig_output = f"""{{% extends 'layouts/vertical.html.twig' %}}

{twig_title_block}

{{% block styles %}}
{styles_html}
{{% endblock %}}

{{% block content %}}
{content_section}
{{% endblock %}}

{{% block scripts %}}
{scripts_html}
{{% endblock %}}
    """
                twig_output = clean_relative_asset_paths(twig_output)
                twig_output = replace_html_links(twig_output, '')

                file.write_text(twig_output.strip() + "\n", encoding="utf-8")

            Log.converted(str(file))
            count += 1

        Log.info(f"{count} files converted in {self.project_pages_path}")

    def _add_home_controller(self):
        """
        Creates src/Controller/HomeController.php with the specified content for Symfony.
        """

        # Ensure the controller directory exists
        self.project_controller_path.mkdir(parents=True, exist_ok=True)

        controller_content = r"""<?php

namespace App\Controller;

use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\Response;
use Symfony\Component\Routing\Annotation\Route;
use Symfony\Component\HttpFoundation\Request;
use Twig\Environment;
use Symfony\Component\HttpKernel\Exception\NotFoundHttpException;

class HomeController extends AbstractController
{

    public function __construct(Environment $twig)
    {
        $this->loader = $twig->getLoader();
    }

    #[Route('/', name: 'home')]
    public function index(): Response
    {
        return $this->render('index.html.twig');
    }

    #[Route('/{path}')]
    public function root($path)
    {
        if ($this->loader->exists($path.'.html.twig')) {
            if ($path == '/' || $path == 'home') {
                die('Home');
            }
            return $this->render($path.'.html.twig');
        }
        throw $this->createNotFoundException();
    }
}
    """
        try:
            with open(self.project_home_controller_path, "w", encoding="utf-8") as f:
                f.write(controller_content.strip() + "\n")
            Log.created(f"controller file at {self.project_home_controller_path}")
        except Exception as e:
            Log.error(f"Failed to create HomeController.php: {e}")

    def _replace_partial_variables(self):
        count = 0
        pattern = re.compile(r'@@(?!if\b|include\b)([A-Za-z_]\w*)\b')

        for file in self.project_partials_path.rglob(f"*{SYMFONY_EXTENSION}"):
            if not file.is_file():
                continue
            try:
                content = file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue

            new_content = pattern.sub(r'{{ (\1) ? \1 : "" }}', content)
            if new_content != content:
                file.write_text(new_content, encoding="utf-8")
                Log.updated(str(file))
                count += 1

        if count:
            Log.info(f"{count} files updated in {self.project_partials_path}")
