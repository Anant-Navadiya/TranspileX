import os
import shutil
import subprocess
from pathlib import Path

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, MVC_DESTINATION_FOLDER, MVC_ASSETS_FOLDER, \
    MVC_PROJECT_CREATION_COMMAND, MVC_GULP_ASSETS_PATH
from transpilex.helpers import copy_assets
from transpilex.helpers.create_gulpfile import create_gulpfile_js
from transpilex.helpers.messages import Messenger
from transpilex.helpers.update_package_json import update_package_json

KEYWORDS = ("@page", "@model")


class CoreToMvcConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=MVC_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name.title()
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / self.project_name
        self.project_assets_path = self.project_root / MVC_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "Views")
        self.project_controllers_path = Path(self.project_root / "Controllers")

        self.core_project_path = Path(f"core/{self.project_name}")
        self.core_project_pages_path = Path(f"core/{self.project_name}/Pages")

        self.create_project()

    def create_project(self):

        if self.core_project_path.exists():
            Messenger.info(f"Core project found at: '{self.core_project_path}'")
        else:
            Messenger.error(f"Core project not found at: '{self.core_project_path}'")
            return

        Messenger.info(f"Creating MVC project at: '{self.project_root}'...")

        self.project_root.mkdir(parents=True, exist_ok=True)

        try:
            subprocess.run(
                f'{MVC_PROJECT_CREATION_COMMAND} {self.project_name}',
                cwd=self.project_root.parent,
                shell=True,
                check=True
            )
            Messenger.success(f"MVC project created successfully.")

            subprocess.run(
                f'dotnet new sln -n {self.project_name}',
                cwd=self.project_root.parent,
                shell=True,
                check=True
            )

            sln_file = f"{self.project_name}.sln"

            subprocess.run(
                f'dotnet sln {sln_file} add {Path(self.project_name) / self.project_name}.csproj',
                cwd=self.project_root.parent,
                shell=True,
                check=True
            )

            Messenger.success(f".sln file created successfully.")

        except subprocess.CalledProcessError:
            Messenger.error("Could not create MVC project.")
            return

        self.project_views_path.mkdir(parents=True, exist_ok=True)

        self._convert()

        self._create_controllers(['Shared'])

        copy_assets(self.assets_path, self.project_assets_path)

        create_gulpfile_js(self.project_root, MVC_GULP_ASSETS_PATH)

        # update_package_json(self.source_path, self.project_root, self.project_name)

        Messenger.completed(f"Project '{self.project_name}' setup", str(self.project_root))

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

                        print(f"Converted to MVC: {src_path} -> {dest_path}")
                    except IOError as e:
                        print(f"Error processing {src_path}: {e}")

    def _create_controllers(self, ignore_list=None):
        ignore_list = ignore_list or []

        # 🔥 Remove Controllers folder if it exists
        if os.path.isdir(self.project_controllers_path):
            print(f"🧹 Removing existing Controllers folder: {self.project_controllers_path}")
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
