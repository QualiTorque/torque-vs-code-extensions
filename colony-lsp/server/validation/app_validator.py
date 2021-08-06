import pathlib
import re

from pygls.lsp.types.basic_structures import DiagnosticSeverity
from server.ats.trees.app import AppTree
from server.validation.common import ValidationHandler
from server.utils import applications


class AppValidationHandler(ValidationHandler):
    def validate(self):
        super().validate()
        # warnings
        self._check_for_deprecated_properties()
        # errors
        self._validate_script_files_exist()

        return self._diagnostics
    
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
    
    def _check_for_deprecated_properties(self):
        deprecated_properties = {"ostype": "os_type under source"}
        message_dep = "Deprecated property '{}'."
        message_replace = "Please use '{}' instead."
        line_num = 0
        for line in self._document.lines:
            for prop in deprecated_properties.keys():
                found = re.findall('^[^#\\n]*(\\b'+prop+'\\b:)', line)
                if len(found) > 0:
                    col = line.find(prop)
                    message = message_dep.format(prop)
                    if deprecated_properties[prop]:
                        message += " " + message_replace.format(deprecated_properties[prop])
                    self._add_diagnostic_for_range(message,
                                                   range_start_tupple=(line_num, col),
                                                   range_end_tupple=(line_num, col+len(prop)),
                                                   diag_severity=DiagnosticSeverity.Warning)                    
            line_num += 1

    
