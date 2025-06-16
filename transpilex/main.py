import argparse

from transpilex.frameworks.cakephp import create_cakephp_project
from transpilex.frameworks.codeigniter import create_codeigniter_project
from transpilex.frameworks.node import create_node_project
from transpilex.frameworks.php import create_php_project

# Constants
SOURCE_FOLDER = './html'
ASSETS_FOLDER = './assets'
SUPPORTED_FRAMEWORKS = ['php', 'codeigniter', 'cakephp','node']


def process_framework(framework_name, project_name, source_folder, assets_folder):
    """Process the selected framework"""
    framework_handlers = {
        'php': lambda: create_php_project(project_name, source_folder, assets_folder),
        'codeigniter': lambda: create_codeigniter_project(project_name, source_folder, assets_folder),
        'cakephp': lambda: create_cakephp_project(project_name, source_folder, assets_folder),
        'node': lambda: create_node_project(project_name, source_folder, assets_folder),
    }

    handler = framework_handlers.get(framework_name)
    if handler:
        handler()
    else:
        print(f'Framework {framework_name} is not implemented yet')

def main():
    parser = argparse.ArgumentParser(description="Generate given frameworks from HTML.")
    parser.add_argument("project", help="Name of the project")
    parser.add_argument("framework",choices=SUPPORTED_FRAMEWORKS, help="Name of the framework")
    parser.add_argument("--src", default=SOURCE_FOLDER, help="Source HTML directory")
    parser.add_argument("--assets", default=ASSETS_FOLDER, help="Assets directory")

    args = parser.parse_args()

    process_framework(args.framework, args.project, args.src, args.assets)


if __name__ == "__main__":
    main()