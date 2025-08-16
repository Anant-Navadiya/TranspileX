import argparse
import sys

from transpilex.config.package import PACKAGE_VERSION
from transpilex.frameworks.php import PHPConverter
from transpilex.frameworks.laravel import LaravelConverter
from transpilex.frameworks.cakephp import CakePHPConverter
from transpilex.frameworks.codeigniter import CodeIgniterConverter
from transpilex.frameworks.symfony import SymfonyConverter
from transpilex.frameworks.node import NodeConverter
from transpilex.frameworks.django import DjangoConverter
from transpilex.frameworks.flask import FlaskConverter
from transpilex.frameworks.ror import RoRConverter
from transpilex.frameworks.spring import SpringConverter
from transpilex.frameworks.core import CoreConverter
from transpilex.frameworks.mvc import MVCConverter
from transpilex.frameworks.blazor import BlazorConverter
from transpilex.frameworks.core_to_mvc import CoreToMvcConverter
from transpilex.helpers.logs import Log

from transpilex.helpers.system_check import system_check

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, SUPPORTED_FRAMEWORKS


def main():
    parser = argparse.ArgumentParser(
        description="Transpilex CLI – Convert static HTML projects into dynamic frameworks.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument('--version', action='version', version=f"v{PACKAGE_VERSION}")
    parser.add_argument('--check', action='store_true', help="Run a system check.")
    parser.add_argument('--list', action='store_true', help="List all supported frameworks.")

    parser.add_argument("project", help="The name for your new project.", nargs='?', default=None)

    subparsers = parser.add_subparsers(dest="framework", help="The target framework.")

    def add_common_framework_args(sp):
        sp.add_argument("--source", default=SOURCE_PATH, help="Path to the source HTML files.")
        sp.add_argument("--assets", default=ASSETS_PATH, help="Name of the assets folder within the source path.")

    # php
    php_p = subparsers.add_parser("php", help="Convert to PHP")
    add_common_framework_args(php_p)
    php_p.add_argument("--no-gulp", action='store_true')
    php_p.add_argument("--no-plugins-config", action='store_true')

    # laravel
    laravel_p = subparsers.add_parser("laravel", help="Convert to Laravel")
    add_common_framework_args(laravel_p)
    laravel_p.add_argument("--auth", action='store_true')

    # cakephp
    cakephp_p = subparsers.add_parser("cakephp", help="Convert to CakePHP")
    add_common_framework_args(cakephp_p)
    cakephp_p.add_argument("--no-gulp", action='store_true')
    cakephp_p.add_argument("--no-plugins-config", action='store_true')

    # codeigniter
    codeigniter_p = subparsers.add_parser("codeigniter", help="Convert to CodeIgniter")
    add_common_framework_args(codeigniter_p)
    codeigniter_p.add_argument("--no-gulp", action='store_true')
    codeigniter_p.add_argument("--no-plugins-config", action='store_true')

    # symfony
    symfony_p = subparsers.add_parser("symfony", help="Convert to Symfony")
    add_common_framework_args(symfony_p)
    symfony_p.add_argument("--no-gulp", action='store_true')
    symfony_p.add_argument("--no-plugins-config", action='store_true')

    # node
    node_p = subparsers.add_parser("node", help="Convert to Node")
    add_common_framework_args(node_p)
    node_p.add_argument("--no-gulp", action='store_true')
    node_p.add_argument("--no-plugins-config", action='store_true')

    # django
    django_p = subparsers.add_parser("django", help="Convert to Django")
    add_common_framework_args(django_p)
    django_p.add_argument("--no-gulp", action='store_true')
    django_p.add_argument("--no-plugins-config", action='store_true')
    django_p.add_argument("--auth", action='store_true')

    # flask
    flask_p = subparsers.add_parser("flask", help="Convert to Flask")
    add_common_framework_args(flask_p)
    flask_p.add_argument("--no-gulp", action='store_true')
    flask_p.add_argument("--no-plugins-config", action='store_true')
    flask_p.add_argument("--auth", action='store_true')

    # ror
    ror_p = subparsers.add_parser("ror", help="Convert to RoR")
    add_common_framework_args(ror_p)

    # spring
    spring_p = subparsers.add_parser("spring", help="Convert to Spring Boot")
    add_common_framework_args(spring_p)
    spring_p.add_argument("--no-gulp", action='store_true')
    spring_p.add_argument("--no-plugins-config", action='store_true')

    # core
    core_p = subparsers.add_parser("core", help="Convert to Core")
    add_common_framework_args(core_p)
    core_p.add_argument("--no-gulp", action='store_true')
    core_p.add_argument("--no-plugins-config", action='store_true')

    # mvc
    mvc_p = subparsers.add_parser("mvc", help="Convert to MVC")
    add_common_framework_args(mvc_p)
    mvc_p.add_argument("--no-gulp", action='store_true')
    mvc_p.add_argument("--no-plugins-config", action='store_true')

    # blazor
    blazor_p = subparsers.add_parser("blazor", help="Convert to MVC")
    add_common_framework_args(blazor_p)
    blazor_p.add_argument("--no-gulp", action='store_true')
    blazor_p.add_argument("--no-plugins-config", action='store_true')

    args = parser.parse_args()

    if args.check:
        system_check(args)
        return
    if args.list:
        Log.success("Supported frameworks:")
        if subparsers.choices:
            for sp_name in (subparsers.choices.keys()):
                Log.info(f"- {sp_name}")
        return

    if not args.project or not args.framework:
        parser.print_help()
        # Add a more explicit error message
        Log.error("Error: The following arguments are required for conversion: project, framework")
        sys.exit(1)

    handler_args = {
        "project_name": args.project,
        "source_path": args.source,
        "assets_path": args.assets
    }

    def make_class_handler(cls):
        return lambda: cls(**handler_args, **framework_specific_kwargs(args))

    handlers = {
        'php': make_class_handler(PHPConverter),
        'laravel': make_class_handler(LaravelConverter),
        'cakephp': make_class_handler(CakePHPConverter),
        'codeigniter': make_class_handler(CodeIgniterConverter),
        'symfony': make_class_handler(SymfonyConverter),
        'node': make_class_handler(NodeConverter),
        'django': make_class_handler(DjangoConverter),
        'flask': make_class_handler(FlaskConverter),
        'ror': make_class_handler(RoRConverter),
        'spring': make_class_handler(SpringConverter),
        'core': make_class_handler(CoreConverter),
        'mvc': make_class_handler(MVCConverter),
        'blazor': make_class_handler(BlazorConverter),
        'core-to-mvc': make_class_handler(CoreToMvcConverter),
    }

    handler = handlers.get(args.framework)
    if not handler:
        Log.error(f"Framework '{args.framework}' is not implemented yet.")
        return

    handler()


def framework_specific_kwargs(args):
    """
    Extract only the flags relevant to the chosen subparser.
    Keep it explicit to avoid leaking unrelated args.
    """
    kwargs = {}
    if hasattr(args, 'no_gulp'):
        kwargs['include_gulp'] = not args.no_gulp
    if hasattr(args, 'no_plugins_config'):
        kwargs['plugins_config'] = not args.no_plugins_config
    if hasattr(args, 'auth'):
        kwargs['auth'] = args.auth
    return kwargs
