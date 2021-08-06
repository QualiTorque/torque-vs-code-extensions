import pathlib
import re
from server.ats.trees.service import ServiceTree
from server.validation.common import ValidationHandler
import sys
import logging
from pygls.lsp.types.basic_structures import DiagnosticSeverity
from server.utils import services


class ServiceValidationHandler(ValidationHandler):
    def validate(self):
        super().validate()

        try:
            # warnings
            self._check_for_unused_service_inputs()
            self._validate_variables_file_exist()
            self._check_for_deprecated_properties()

        except Exception as ex:
            print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)

        return self._diagnostics

    def _get_repo_root_path(self):
        path = pathlib.Path(self._document.path).absolute()
        if path.parents[1].name == "services":
            return path.parents[2].absolute().as_posix()

        else:
            raise ValueError(f"Wrong document path of service file: {path.as_posix()}")    

    def _check_for_unused_service_inputs(self):
        if self._tree.inputs_node:
            message = "Unused variable {}"
            source = self._document.source
            for input in self._tree.inputs_node.nodes:
                found = re.findall('^[^#\\n]*(\$\{'+input.key.text+'\}|\$'+input.key.text+'\\b)', source, re.MULTILINE)
                if len(found) == 0:
                    self._add_diagnostic(
                        input.key,
                        message=message.format(input.key.text),
                        diag_severity=DiagnosticSeverity.Warning
                    )

    def _validate_variables_file_exist(self):
        vars = services.get_service_vars(self._document.path)
        vars_files = [var["file"] for var in vars]
        tree: ServiceTree = self._tree

        if tree.variables is None:
            return

        node = tree.variables.var_file
        if node:
            if not node.text:
                self._add_diagnostic(node, f"Provide a filename")
                return

            if node.text not in vars_files:
                self._add_diagnostic(node, f"File {node.text} doesn't exist")
    
    def _check_for_deprecated_properties(self):
        deprecated_properties = {"tfvars_file": "var_file under variables"}
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
