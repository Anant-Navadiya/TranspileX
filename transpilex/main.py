import argparse

from transpilex.config.package import PACKAGE_VERSION
from transpilex.frameworks.blazor import BlazorConverter
from transpilex.frameworks.cakephp import CakePHPConverter
from transpilex.frameworks.codeigniter import CodeIgniterConverter
from transpilex.frameworks.core import create_core_project
from transpilex.frameworks.core_to_mvc import CoreToMvcConverter
from transpilex.frameworks.django import create_django_project
from transpilex.frameworks.flask import create_flask_project
from transpilex.frameworks.laravel import LaravelConverter
from transpilex.frameworks.mvc import create_mvc_project
from transpilex.frameworks.node import create_node_project
from transpilex.frameworks.php import PHPConverter
from transpilex.frameworks.ror import RoRConverter
from transpilex.frameworks.spring import SpringConverter
from transpilex.frameworks.symfony import create_symfony_project
from transpilex.helpers.messages import Messenger

from transpilex.helpers.system_check import system_check

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, SUPPORTED_FRAMEWORKS


def process_framework(args):
    """
    Initializes and runs the correct framework converter based on CLI arguments.
    """
    framework_name = args.framework

    handler_args = {
        "project_name": args.project,
        "source_path": args.src,
        "assets_path": args.assets,
        "include_gulp": not args.no_gulp
    }

    # Simplified handlers using a dictionary of keyword arguments
    def make_class_handler(cls):
        return lambda: cls(**handler_args)

    def make_func_handler(func):
        return lambda: func(
            handler_args["project_name"],
            handler_args["source_path"],
            handler_args["assets_path"]
        )

    # Map framework names to their corresponding handlers
    handlers = {
        'php': make_class_handler(PHPConverter),
        'laravel': make_class_handler(LaravelConverter),
        'cakephp': make_class_handler(CakePHPConverter),
        'codeigniter': make_class_handler(CodeIgniterConverter),
        'ror': make_class_handler(RoRConverter),
        'blazor': make_class_handler(BlazorConverter),
        'core-to-mvc': make_class_handler(CoreToMvcConverter),
        'spring': make_class_handler(SpringConverter),

        'symfony': make_func_handler(create_symfony_project),
        'node': make_func_handler(create_node_project),
        'django': make_func_handler(create_django_project),
        'flask': make_func_handler(create_flask_project),
        'core': make_func_handler(create_core_project),
        'mvc': make_func_handler(create_mvc_project),
    }

    handler = handlers.get(framework_name)
    if handler:
        handler()
    else:
        Messenger.error(f"Framework '{framework_name}' is not implemented yet.")


def main():
    """
    Main entry point for the Transpilex CLI.
    """
    parser = argparse.ArgumentParser(
        description="Transpilex CLI – Convert static HTML projects into dynamic frameworks.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--version', action='version', version=f"v{PACKAGE_VERSION}")

    # --- Commands as flags ---
    parser.add_argument('--check', action='store_true', help='Check system for framework prerequisites.')
    parser.add_argument('--list', action='store_true', help='List all supported frameworks.')

    # --- Default generation arguments ---
    parser.add_argument("project", nargs='?', help="Name for the new project (e.g., 'my-awesome-site').")
    parser.add_argument("framework", nargs='?', choices=SUPPORTED_FRAMEWORKS, help="Target framework to convert to.")
    parser.add_argument("--src", default=SOURCE_PATH, help=f"Source HTML directory (default: {SOURCE_PATH}).")
    parser.add_argument("--assets", default=ASSETS_PATH, help=f"Source assets directory (default: {ASSETS_PATH}).")
    parser.add_argument("--no-gulp", action='store_true',
                        help="Disable creation of Gulpfile and package.json dependencies.")

    args = parser.parse_args()

    if args.check:
        system_check(args)
    elif args.list:
        print("Supported frameworks:")
        for framework in sorted(SUPPORTED_FRAMEWORKS):
            print(f"  - {framework}")
    elif args.project and args.framework:
        process_framework(args)
    else:
        parser.print_help()
