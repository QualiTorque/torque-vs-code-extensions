import pathlib

from server.ats.trees.common import BaseTree
from server.utils.common import ResourcesManager

APPLICATIONS = {}


class ApplicationsManager(ResourcesManager):
    resource_folder = "applications"
    resource_type = "application"
    cache = APPLICATIONS

    @staticmethod
    def build_completion_text(resource_name: str, resource_tree: BaseTree):
        output = ResourcesManager.build_completion_text(resource_name, resource_tree)
        output += "    instances: 1\n"
        return output

    @staticmethod
    def get_app_scripts(app_path: str):
        scripts = []
        files = pathlib.Path(app_path.replace("file://", "")).parent.glob("./*")
        for file in files:
            if not file.name.endswith(".yaml"):
                scripts.append(pathlib.Path(file).name)

        return scripts
