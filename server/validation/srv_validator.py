import logging
import re
import sys

from pygls.lsp.types.basic_structures import DiagnosticSeverity

from server.ats.trees.service import ServiceTree
from server.utils.services import ServicesManager as services
from server.validation.common import ValidationHandler


class ServiceValidationHandler(ValidationHandler):
    def validate(self):
        super().validate()

        try:
            # warnings
            deprecated_properties = {"tfvars_file": "var_file under variables"}

            self._check_for_unused_service_inputs()
            self._validate_variables_file_exist()
            self._check_for_deprecated_properties(deprecated_properties)

        except Exception as ex:
            print(
                "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
                type(ex).__name__,
                ex,
            )
            logging.error(
                "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
                type(ex).__name__,
                ex,
            )

        return self._diagnostics

    def _check_for_unused_service_inputs(self):
        if self._tree.inputs_node:
            message = "Unused variable {}"
            source = self._document.source
            name_only_var_values = []

            if self._tree.variables:
                for var in self._tree.variables.get_values():
                    if not var.value:
                        name_only_var_values.append(var.key.text)

            for input in self._tree.get_inputs():
                found = re.findall('^[^#\\n]*(\$\{'+input.key.text+'\}|\$'+input.key.text+'\\b)', source, re.MULTILINE)
                if len(found) == 0 and input.key.text not in name_only_var_values:
                    self._add_diagnostic(
                        input.key,
                        message=message.format(input.key.text),
                        diag_severity=DiagnosticSeverity.Warning,
                    )

    def _validate_variables_file_exist(self):
        vars = services.get_service_vars(self._document.path)
        vars_files = [var["file"] for var in vars]
        tree: ServiceTree = self._tree

        if tree.variables is None:
            return

        node = tree.variables.var_file
        if node:
            if not node.value:
                self._add_diagnostic(node.key, "Provide a filename")
                return

            if node.text not in vars_files:
                self._add_diagnostic(node.value, f"File {node.text} doesn't exist")
