import pathlib
import re
from server.ats.trees.service import ServiceTree
from server.validation.common import ValidationHandler
import sys
import logging
from typing import List
from pygls.lsp.types.basic_structures import DiagnosticSeverity
from server.constants import PREDEFINED_COLONY_INPUTS
from server.utils import services


class ServiceValidationHandler(ValidationHandler):
    def validate(self, text_doc):
        super().validate()

        try:
            # warnings
            self._check_for_unused_service_inputs(text_doc)

        except Exception as ex:
            print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)

        return self._diagnostics

    def _get_repo_root_path(self):
        path = pathlib.Path(self._document_path).absolute()
        if path.parents[1].name == "services":
            return path.parents[2].absolute().as_posix()

        else:
            raise ValueError(f"Wrong document path of service file: {path.as_posix()}")    

    def _check_for_unused_service_inputs(self, text_doc):
        if hasattr(self._tree, 'inputs_node') and self._tree.inputs_node:
            message = "Unused variable {}"
            source = text_doc.source
            for input in self._tree.inputs_node.nodes:
                found = re.findall('^(?!.*#).*(\$\{'+input.key.text+'\}|\$'+input.key.text+'\\b)', source, re.MULTILINE)
                if len(found) == 0:
                    self._add_diagnostic(
                        input.key,
                        message=message.format(input.key.text),
                        diag_severity=DiagnosticSeverity.Warning
                    )

    def _validate_variables_file_exist(self):
        vars = services.get_service_vars(self._document_path)
        vars_files = [var["file"] for var in vars]
        tree: ServiceTree = self._tree

        if tree.variables is None:
            return

        node = tree.variables.var_file
        if node is not None:
            if node.text:
                self._add_diagnostic(node, f"File {node.text} doesn't exist")
            else:
                self._add_diagnostic(node, f"Provide a filename")
    
    def validate(self, text_doc):
        super().validate()
        # errors
        self._validate_variables_file_exist()

        return self._diagnostics

        