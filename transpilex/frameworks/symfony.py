import re
import json
import subprocess
from pathlib import Path
from bs4 import BeautifulSoup

from transpilex.helpers import copy_assets, change_extension_and_copy
from transpilex.helpers.clean_relative_asset_paths import clean_relative_asset_paths
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.replace_html_links import replace_html_links
from transpilex.helpers.update_package_json import update_package_json


def add_home_controller_file(project_root):
    """
    Creates src/Controller/HomeController.php with the specified content for Symfony.
    """
    controller_dir = project_root / "src" / "Controller"
    controller_file_path = controller_dir / "HomeController.php"

    # Ensure the controller directory exists
    controller_dir.mkdir(parents=True, exist_ok=True)

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
        with open(controller_file_path, "w", encoding="utf-8") as f:
            f.write(controller_content.strip() + "\n")
        print(f"✅ Created controller file: {controller_file_path.relative_to(project_root)}")
    except Exception as e:
        print(f"❌ Error writing to {controller_file_path}: {e}")


def extract_json_from_include(include_str):
    try:
        match = re.search(r'\{.*\}', include_str)
        if match:
            json_text = match.group().replace("'", '"')
            return json.loads(json_text)
    except Exception:
        pass
    return {}


def convert_to_symfony_twig(dist_folder):
    dist_path = Path(dist_folder)
    count = 0

    for file in dist_path.rglob("*.html.twig"):  # Target .html.twig files
        if file.is_file():
            print(f"Processing for Symfony Twig: {file.name}")
            with open(file, "r", encoding="utf-8") as f:
                content = f.read()

            soup = BeautifulSoup(content, 'html.parser')

            # Extract title from title-meta include (from original HTML)
            # Assuming @@include('./partials/title-meta.html', {'title': '...' }) syntax
            title_meta_match = re.search(r'@@include\(["\']\.\/partials\/title-meta\.html["\']\s*,\s*({.*?})\)',
                                         content)
            twig_title_block = ""
            if title_meta_match:
                meta_data = extract_json_from_include(title_meta_match.group())
                layout_title = meta_data.get("title", "").strip()
                if layout_title:
                    twig_title_block = f"{{% block title %}}{layout_title}{{% endblock %}}"

            # Extract <link> tags for stylesheets
            link_tags = soup.find_all("link", rel="stylesheet")  # Only get stylesheets
            stylesheets_html = "\n".join(f"    {str(link)}" for link in link_tags)

            # Extract <script> tags
            script_tags = soup.find_all("script")
            scripts_html = "\n".join(f"    {str(tag)}" for tag in script_tags)

            # Locate content with data-content
            content_div = soup.find(attrs={"data-content": True})
            if not content_div:
                print(f"⚠️ Skipping '{file.name}': no data-content found.")
                continue
            inner_html = content_div.decode_contents()

            # Replace page-title include (from original HTML) with Twig include
            # @@include('./partials/page-title.html', {'title': '...', 'subtitle': '...'})
            page_title_match = re.search(r'@@include\(\s*["\']\.\/partials\/page-title\.html["\']\s*,\s*({.*?})\s*\)',
                                         inner_html)
            if page_title_match:
                page_data = extract_json_from_include(page_title_match.group())
                page_title = page_data.get("title", "").strip()
                subtitle = page_data.get("subtitle", "").strip()

                # Format for Twig include syntax
                twig_page_title_include = f"{{{{ include('partials/page-title.html.twig', {{subTitle: '{subtitle}', title: '{page_title}'}}) }}}}"
                inner_html = re.sub(r'@@include\(\s*["\']\.\/partials\/page-title\.html["\']\s*,\s*{.*?}\s*\)',
                                    twig_page_title_include, inner_html)
            else:
                # Clean up any leftover partials include if no match for page-title
                inner_html = re.sub(r'@@include\(\s*["\']\.\/partials\/page-title\.html["\'].*?\)', '', inner_html)

            # Remove @@include('./partials/footer.html') from inner_html
            inner_html = re.sub(r'@@include\(\s*["\']\.\/partials\/footer\.html["\'].*?\)', '', inner_html)

            content_section = inner_html.strip()

            # Final Twig structure
            twig_output = f"""{{% extends 'layouts/vertical.html.twig' %}}

{twig_title_block}

{{% block stylesheets %}}
{stylesheets_html}
{{% endblock %}}

{{% block content %}}
{content_section}
{{% endblock %}}

{{% block scripts %}}
{scripts_html}
{{% endblock %}}
"""
            # Clean asset paths
            twig_output = clean_relative_asset_paths(twig_output)

            # replace .html
            content = replace_html_links(content, '')

            with open(file, "w", encoding="utf-8") as f:
                f.write(twig_output.strip() + "\n")

            print(f"✅ Converted: {file.relative_to(dist_path)}")
            count += 1

    print(f"\n✨ {count} Twig files converted successfully.")


def create_symfony_project(project_name, source_folder, assets_folder):

    project_root = Path("symfony") / project_name
    project_root.parent.mkdir(parents=True, exist_ok=True)

    # Create the Symfony project using Composer
    print(f"📦 Creating Symfony project '{project_root}'...")
    try:
        subprocess.run(
            f'symfony new {project_root} --version="7.3.x-dev" --webapp',
            shell=True,
            check=True
        )
        print("✅ Symfony project created successfully.")

    except subprocess.CalledProcessError:
        print("❌ Error: Could not create Symfony project. Make sure Composer and PHP are set up correctly.")
        return

    # Copy the source file and change extensions
    pages_path = project_root / "templates"
    pages_path.mkdir(parents=True, exist_ok=True)

    change_extension_and_copy('html.twig', source_folder, pages_path)

    convert_to_symfony_twig(pages_path)

    add_home_controller_file(project_root)

    # Copy assets to webroot while preserving required files
    assets_path = project_root / "public"
    copy_assets(assets_folder, assets_path, preserve=["index.php"])

    # Create gulpfile.js
    create_gulpfile_js(project_root, './public')

    # Update dependencies
    update_package_json(source_folder, project_root, project_name)

    print(f"\n🎉 Project '{project_name}' setup complete at: {project_root}")