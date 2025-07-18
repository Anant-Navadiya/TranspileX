from pathlib import Path
import requests, zipfile, io

from transpilex.config.base import ASSETS_PATH, SOURCE_PATH, SPRING_DESTINATION_FOLDER


class SpringConverter:
    def __init__(self, project_name, source_path=SOURCE_PATH, destination_folder=SPRING_DESTINATION_FOLDER,
                 assets_path=ASSETS_PATH):
        self.project_name = project_name
        self.source_path = Path(source_path)
        self.destination_path = Path(destination_folder)
        self.assets_path = Path(assets_path)

        self.project_root = self.destination_path / self.project_name
        # self.project_assets_path = self.project_root / CAKEPHP_ASSETS_FOLDER
        # self.project_pages_path = Path(self.project_root / "templates" / "Pages")
        # self.project_element_path = Path(self.project_root / "templates" / "element")
        # self.project_pages_controller_path = Path(self.project_root / "src" / "Controller" / "PagesController.php")
        # self.project_routes_path = Path(self.project_root / "config" / "routes.php")

        self.create_project()

    def create_project(self):

        params = {
            "type": "maven-project",
            "language": "java",
            "bootVersion": "3.5.3",
            "baseDir": self.project_name,
            "groupId": "com",
            "artifactId": self.project_name,
            "name": self.project_name,
            "packageName": f"com.{self.project_name}",
            "packaging": "jar",
            "javaVersion": "24",
            "dependencies": "web,thymeleaf,devtools",
        }

        r = requests.get("https://start.spring.io/starter.zip", params=params)
        z = zipfile.ZipFile(io.BytesIO(r.content))
        z.extractall(self.project_name)
