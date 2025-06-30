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
    def make_args_handler(func):
        return lambda: func(project_name, source_folder, assets_folder)

    def make_class_handler(cls):
        return lambda: cls(project_name)

    handlers = {
        'laravel': make_args_handler(create_laravel_project),
        'codeigniter': make_args_handler(create_codeigniter_project),
        'symfony': make_args_handler(create_symfony_project),
        'node': make_args_handler(create_node_project),
        'django': make_args_handler(create_django_project),
        'flask': make_args_handler(create_flask_project),
        'core': make_args_handler(create_core_project),
        'mvc': make_args_handler(create_mvc_project),
        'php': make_class_handler(PHPConverter),
        'cakephp': make_class_handler(CakePHPConverter),
        'core-to-mvc': make_class_handler(CoreToMvcConverter),
    }

    handler = handlers.get(framework_name)
    if handler:
        handler()
    else:
        print(f"Framework '{framework_name}' is not implemented yet.")


def run_generate(args):
    process_framework(args.framework, args.project, args.src, args.assets)


def main():
    parser = argparse.ArgumentParser(description="Transpilex CLI – Convert HTML into frameworks")
    parser.add_argument('--version', action='version', version=PACKAGE_VERSION)

    # CLI flags for system commands
    parser.add_argument('--system-check', action='store_true', help="Show prerequisites for all frameworks")
    parser.add_argument('--supported-frameworks', action='store_true', help="Show all supported frameworks")

    # Default positional args for project generation
    parser.add_argument("project", nargs='?', help="Name of the project")
    parser.add_argument("framework", nargs='?', choices=SUPPORTED_FRAMEWORKS, help="Target framework")
    parser.add_argument("--src", default=SOURCE_PATH, help="Source HTML directory")
    parser.add_argument("--assets", default=ASSETS_PATH, help="Assets directory")

    args = parser.parse_args()

    if args.system_check:
        system_check(args)
    elif args.supported_frameworks:
        print("✔ Supported frameworks:\n- " + "\n- ".join(SUPPORTED_FRAMEWORKS))
    elif args.project and args.framework:
        run_generate(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
