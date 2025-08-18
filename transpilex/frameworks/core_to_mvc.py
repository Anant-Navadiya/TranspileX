import os
import shutil
import subprocess
from pathlib import Path

from transpilex.config.base import MVC_DESTINATION_FOLDER, MVC_ASSETS_FOLDER, \
    MVC_PROJECT_CREATION_COMMAND, MVC_GULP_ASSETS_PATH, SLN_FILE_CREATION_COMMAND
from transpilex.helpers import copy_assets
from transpilex.helpers.gulpfile import add_gulpfile
from transpilex.helpers.logs import Log
from transpilex.helpers.package_json import update_package_json
from transpilex.helpers.plugins_file import plugins_file
from transpilex.helpers.validations import folder_exists

KEYWORDS = ("@page", "@model")


class CoreToMvcConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str):
        self.project_name = project_name.title()
        self.source_path = Path(source_path)
        self.destination_path = Path(MVC_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)

        self.project_root = self.destination_path / self.project_name
        self.project_assets_path = self.project_root / MVC_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "Views")
        self.project_controllers_path = Path(self.project_root / "Controllers")

        self.core_project_path = Path(f"core/{self.project_name}")
        self.core_project_pages_path = Path(f"core/{self.project_name}/Pages")
        self.core_project_shared_path = Path(f"core/{self.project_name}/Shared")
        self.core_project_partials_path = Path(f"core/{self.project_name}/Shared/Partials")
        self.core_project_assets_path = Path(f"core/{self.project_name}/wwwroot")

        self.create_project()

    def create_project(self):

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        if folder_exists(self.core_project_path):
            Log.info(f"Core project found at: {self.core_project_path}")
        else:
            Log.error(f"Core project not found at: '{self.core_project_path}'")
            return

        Log.project_start(self.project_name)

        self.project_root.mkdir(parents=True, exist_ok=True)

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

        self.project_views_path.mkdir(parents=True, exist_ok=True)

        self._convert()

        self._create_controllers(['Shared'])

        copy_assets(self.core_project_assets_path, self.project_assets_path)

        # if self.include_gulp:
        #     has_plugins_file = plugins_file(self.source_path, self.project_root)
        #     add_gulpfile(self.project_root, MVC_GULP_ASSETS_PATH, has_plugins_file)
        #     update_package_json(self.source_path, self.project_root, self.project_name)

        Log.project_end(self.project_name, str(self.project_root))

    def _convert(self):
        for root, _, files in os.walk(self.core_project_pages_path):
            for file in files:
                if file.endswith(".cshtml") and not file.endswith(".cshtml.cs"):
                    src_path = os.path.join(root, file)
                    relative_path = os.path.relpath(src_path, self.core_project_pages_path)
                    dest_path = os.path.join(self.project_views_path, relative_path)

                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

                    try:
                        with open(src_path, "r", encoding="utf-8", errors="ignore") as f:
                            lines = f.readlines()

                        filtered_lines = [
                            line for line in lines
                            if not any(line.strip().startswith(keyword) for keyword in KEYWORDS)
                        ]

                        with open(dest_path, "w", encoding="utf-8") as f:
                            f.writelines(filtered_lines)
                        Log.converted(dest_path)
                    except IOError as e:
                        Log.error(f"Error processing {src_path}: {e}")

    def _create_controllers(self, ignore_list=None):
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
                print(f"✅ Created: {controller_file_path}")

        print("✨ Controller generation completed.")

    def _create_controller_file(self, path, controller_name, actions):
        """Creates a controller file with basic action methods."""
        using_statements = "using Microsoft.AspNetCore.Mvc;"

        action_methods = "\n\n".join([
            f"""        public IActionResult {action}()\n        {{\n            return View();\n        }}"""
            for action in actions
        ])

        controller_class = f"""
    namespace {self.project_name}.Controllers
    {{
        public class {controller_name}Controller : Controller
        {{
    {action_methods}
        }}
    }}
    """.strip()

        with open(path, "w", encoding="utf-8") as f:
            f.write(using_statements + "\n\n" + controller_class)
