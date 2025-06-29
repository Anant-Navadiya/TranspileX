import re
import json
import subprocess
from pathlib import Path

from transpilex.config.base import SOURCE_PATH, ASSETS_PATH, MVC_DESTINATION_FOLDER, MVC_ASSETS_FOLDER
from transpilex.helpers.messages import Messenger


class CoreToMvcConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=MVC_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name.title()
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / project_name
        self.project_assets_path = self.project_root / MVC_ASSETS_FOLDER
        self.project_views_path = Path(self.project_root / "Views")

        self.core_project_path = Path(f"core/{self.project_name}")

        self.create_project()

    def create_project(self):

        if self.core_project_path.exists():
            Messenger.info(f"Core project found at: '{self.core_project_path}'")
        else:
            Messenger.error(f"Core project not found at: '{self.core_project_path}'")
            return

        Messenger.info(f"Creating MVC project at: '{self.project_root}'...")

        self.project_root.mkdir(parents=True, exist_ok=True)