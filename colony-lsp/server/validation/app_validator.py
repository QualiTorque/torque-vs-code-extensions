import pathlib
from server.ats.trees.app import AppTree
from server.validation.common import ValidationHandler
from server.utils import applications


class AppValidationHandler(ValidationHandler):
    def _validate_script_files_exist(self):
        scripts = applications.get_app_scripts(self._document.path)
        tree: AppTree = self._tree
        if tree.configuration is None:
            return
            
        for prop in ['initialization', 'start', 'healthcheck']:
            node = getattr(tree.configuration, prop)

            if not node or not node.script:
                continue
            
            if not node.script.text:
                self._add_diagnostic(node.script, "No filename provided")
                continue

            if node.script.text not in scripts:
                self._add_diagnostic(node.script, f"File {node.script.text} doesn't exist")


    def _get_repo_root_path(self):
        path = pathlib.Path(self._document.path).absolute()
        if path.parents[1].name == "applications":
            return path.parents[2].absolute().as_posix()

        else:
            raise ValueError(f"Wrong document path of application file: {path.as_posix()}")

    def validate(self):
        super().validate()
        # errors
        self._validate_script_files_exist()

        return self._diagnostics
