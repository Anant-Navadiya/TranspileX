from pathlib import Path
import requests, zipfile, io

from transpilex.config.base import SPRING_DESTINATION_FOLDER, \
    SPRING_BOOT_PROJECT_CREATION_URL, SPRING_BOOT_PROJECT_PARAMS
from transpilex.helpers.logs import Log
from transpilex.helpers.validations import folder_exists


class SpringConverter:
    def __init__(self, project_name: str, source_path: str, assets_path: str):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(SPRING_DESTINATION_FOLDER)
        self.assets_path = Path(self.source_path / assets_path)

        self.project_root = self.destination_path / self.project_name
        # self.project_assets_path = self.project_root / CAKEPHP_ASSETS_FOLDER
        # self.project_pages_path = Path(self.project_root / "templates" / "Pages")
        # self.project_element_path = Path(self.project_root / "templates" / "element")
        # self.project_pages_controller_path = Path(self.project_root / "src" / "Controller" / "PagesController.php")
        # self.project_routes_path = Path(self.project_root / "config" / "routes.php")

        self.create_project()

    def create_project(self):

        if not folder_exists(self.source_path):
            Log.error("Source folder does not exist")
            return

        if folder_exists(self.project_root):
            Log.error(f"Project already exists at: {self.project_root}")
            return

        Log.project_start(self.project_name)

        params = {
            **SPRING_BOOT_PROJECT_PARAMS,
            "baseDir": self.project_name,
            "artifactId": self.project_name,
            "name": self.project_name,
            "packageName": f"com.{self.project_name}",
        }

        try:
            r = requests.get(SPRING_BOOT_PROJECT_CREATION_URL, params=params, timeout=10)
            r.raise_for_status()

            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                z.extractall(self.destination_path)

            Log.success("Spring Boot project created successfully")

        except requests.exceptions.RequestException as e:
            Log.error(f"Network or request error: {e}")

        except zipfile.BadZipFile:
            Log.error("Downloaded file is not a valid ZIP archive")

        except OSError as e:
            Log.error(f"File system error while extracting: {e}")

        except Exception as e:
            Log.error(f"Unexpected error: {e}")
