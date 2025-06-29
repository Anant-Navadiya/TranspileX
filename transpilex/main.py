import argparse

from transpilex.config.package import PACKAGE_VERSION
from transpilex.frameworks.cakephp import CakePHPConverter
# from transpilex.frameworks.cakephp import create_cakephp_project
from transpilex.frameworks.codeigniter import create_codeigniter_project
from transpilex.frameworks.core import create_core_project
from transpilex.frameworks.core_to_mvc import CoreToMvcConverter
from transpilex.frameworks.django import create_django_project
from transpilex.frameworks.flask import create_flask_project
from transpilex.frameworks.laravel import create_laravel_project
from transpilex.frameworks.mvc import create_mvc_project
from transpilex.frameworks.node import create_node_project
from transpilex.frameworks.php import PHPConverter
from transpilex.frameworks.symfony import create_symfony_project

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, SUPPORTED_FRAMEWORKS
from transpilex.helpers.system_check import system_check


def process_framework(framework_name, project_name, source_folder, assets_folder):
    """Process the selected framework"""
    framework_handlers = {
        'laravel': lambda: create_laravel_project(project_name, source_folder, assets_folder),
        'codeigniter': lambda: create_codeigniter_project(project_name, source_folder, assets_folder),
        # 'cakephp': lambda: create_cakephp_project(project_name, source_folder, assets_folder),
        'symfony': lambda: create_symfony_project(project_name, source_folder, assets_folder),
        'node': lambda: create_node_project(project_name, source_folder, assets_folder),
        'django': lambda: create_django_project(project_name, source_folder, assets_folder),
        'flask': lambda: create_flask_project(project_name, source_folder, assets_folder),
        'core': lambda: create_core_project(project_name, source_folder, assets_folder),
        'mvc': lambda: create_mvc_project(project_name, source_folder, assets_folder),
    }

    handler = framework_handlers.get(framework_name)
    if handler:
        handler()
    elif framework_name == 'php':
        PHPConverter(project_name)
    elif framework_name == 'cakephp':
        CakePHPConverter(project_name)
    elif framework_name == 'core-to-mvc':
        CoreToMvcConverter(project_name)
    else:
        print(f'Framework {framework_name} is not implemented yet')


def run_generate(args):
    process_framework(args.framework, args.project, args.src, args.assets)


def main():
    parser = argparse.ArgumentParser(description="Transpilex CLI – Convert HTML into frameworks")

    parser.add_argument('--version', action='version', version=PACKAGE_VERSION)

    subparsers = parser.add_subparsers(dest="command", required=True)

    # generate command
    generate_parser = subparsers.add_parser("generate", help="Generate code for a given framework")
    generate_parser.add_argument("project", help="Name of the project")
    generate_parser.add_argument("framework", choices=SUPPORTED_FRAMEWORKS, help="Target framework")
    generate_parser.add_argument("--src", default=SOURCE_PATH, help="Source HTML directory")
    generate_parser.add_argument("--assets", default=ASSETS_PATH, help="Assets directory")
    generate_parser.set_defaults(func=run_generate)

    # info command
    info_parser = subparsers.add_parser("system-check", help="Show Prerequisites for all frameworks")
    info_parser.set_defaults(func=system_check)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
