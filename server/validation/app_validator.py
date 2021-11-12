from server.ats.trees.app import AppTree
from server.validation.common import ValidationHandler
from server.utils.applications import ApplicationsManager as applications


class AppValidationHandler(ValidationHandler):
    def validate(self):
        deprecated_properties = {"ostype": "os_type under source"}
        super().validate()
        # warnings
        self._check_for_deprecated_properties(deprecated_properties)
        # errors
        self._validate_script_files_exist()

        return self._diagnostics

    def _validate_script_files_exist(self):
        scripts = applications.get_app_scripts(self._document.path)
        tree: AppTree = self._tree
        if tree.configuration is None:
            return

        for prop in ['initialization', 'start', 'healthcheck']:
            node = getattr(tree.configuration, prop, None)

            if not node or not node.script:
                continue

            if not node.script.value:
                self._add_diagnostic(node.script.key, "No filename provided")
                continue

            if node.script.text not in scripts:
                self._add_diagnostic(node.script.value, f"File {node.script.text} doesn't exist")
