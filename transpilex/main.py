import argparse

from transpilex.config.package import PACKAGE_VERSION
from transpilex.frameworks.blazor import BlazorConverter
from transpilex.frameworks.cakephp import CakePHPConverter
from transpilex.frameworks.codeigniter import CodeIgniterConverter
from transpilex.frameworks.core import create_core_project
from transpilex.frameworks.core_to_mvc import CoreToMvcConverter
from transpilex.frameworks.django import create_django_project, DjangoConverter
from transpilex.frameworks.flask import FlaskConverter
from transpilex.frameworks.laravel import LaravelConverter
from transpilex.frameworks.mvc import create_mvc_project
from transpilex.frameworks.node import NodeConverter
from transpilex.frameworks.php import PHPConverter
from transpilex.frameworks.ror import RoRConverter
from transpilex.frameworks.spring import SpringConverter
from transpilex.frameworks.symfony import SymfonyConverter
from transpilex.helpers.logs import Log

from transpilex.helpers.system_check import system_check

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, SUPPORTED_FRAMEWORKS


def main():
    parser = argparse.ArgumentParser(
        description="Transpilex CLI – Convert static HTML projects into dynamic frameworks."
    )
    parser.add_argument('--version', action='version', version=f"v{PACKAGE_VERSION}")
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--list', action='store_true')

    # First positional: project name
    parser.add_argument("project", help="Project name")

    subparsers = parser.add_subparsers(dest="framework", required=True)

    # helper for subparser common options that should be AFTER framework
    def add_common_framework_args(sp):
        sp.add_argument("--source", default=SOURCE_PATH)
        sp.add_argument("--assets", default=ASSETS_PATH)

    # php
    php_p = subparsers.add_parser("php", help="Convert to PHP")
    add_common_framework_args(php_p)
    php_p.add_argument("--no-gulp", action='store_true')

    # laravel
    laravel_p = subparsers.add_parser("laravel", help="Convert to Laravel")
    add_common_framework_args(laravel_p)
    laravel_p.add_argument("--auth", action='store_true')

    # cakephp
    cakephp_p = subparsers.add_parser("cakephp", help="Convert to CakePHP")
    add_common_framework_args(cakephp_p)
    cakephp_p.add_argument("--no-gulp", action='store_true')

    # codeigniter
    codeigniter_p = subparsers.add_parser("codeigniter", help="Convert to CodeIgniter")
    add_common_framework_args(codeigniter_p)
    codeigniter_p.add_argument("--no-gulp", action='store_true')

    # symfony
    symfony_p = subparsers.add_parser("symfony", help="Convert to Symfony")
    add_common_framework_args(symfony_p)
    symfony_p.add_argument("--no-gulp", action='store_true')

    # node
    node_p = subparsers.add_parser("node", help="Convert to Node")
    add_common_framework_args(node_p)
    node_p.add_argument("--no-gulp", action='store_true')

    # django
    django_p = subparsers.add_parser("django", help="Convert to Django")
    add_common_framework_args(django_p)
    django_p.add_argument("--no-gulp", action='store_true')
    django_p.add_argument("--auth", action='store_true')

    # flask
    flask_p = subparsers.add_parser("flask", help="Convert to Flask")
    add_common_framework_args(flask_p)
    flask_p.add_argument("--no-gulp", action='store_true')
    flask_p.add_argument("--auth", action='store_true')

    args = parser.parse_args()

    if args.check:
        system_check(args)
        return
    if args.list:
        print("Supported frameworks:")
        for sp in subparsers.choices:
            print(f"  - {sp}")
        return
    if not getattr(args, "framework", None):
        parser.print_help()
        return

    handler_args = {
        "project_name": args.project,
        "source_path": args.source,
        "assets_path": args.assets
    }

    def make_class_handler(cls):
        return lambda: cls(**handler_args, **framework_specific_kwargs(args))

    def make_func_handler(func):
        return lambda: func(
            handler_args["project_name"],
            handler_args["source_path"],
            handler_args["assets_path"],
            **framework_specific_kwargs(args)
        )

    handlers = {
        'php': make_class_handler(PHPConverter),
        'laravel': make_class_handler(LaravelConverter),
        'cakephp': make_class_handler(CakePHPConverter),
        'codeigniter': make_class_handler(CodeIgniterConverter),
        'symfony': make_class_handler(SymfonyConverter),
        'node': make_class_handler(NodeConverter),
        'django': make_class_handler(DjangoConverter),
        'flask': make_class_handler(FlaskConverter),

        'core': make_func_handler(create_core_project),
        'mvc': make_func_handler(create_mvc_project),
        'blazor': make_class_handler(BlazorConverter),
        'core-to-mvc': make_class_handler(CoreToMvcConverter),

        'ror': make_class_handler(RoRConverter),
        'spring': make_class_handler(SpringConverter),
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
    if args.framework == "php" or args.framework == "cakephp" or args.framework == "codeigniter" or args.framework == "symfony" or args.framework == "node":
        return {"include_gulp": not args.no_gulp}
    if args.framework == "laravel":
        return {
            "auth": args.auth,
        }
    if args.framework == "flask" or args.framework == "django":
        return {
            "include_gulp": not args.no_gulp,
            "auth": args.auth
        }
    return {}
