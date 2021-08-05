from typing import List
from pygls.lsp.types.basic_structures import Diagnostic, DiagnosticSeverity, Position, Range
from server.ats.trees.common import BaseTree, YamlNode
from server.constants import PREDEFINED_COLONY_INPUTS


class ValidationHandler:
    def __init__(self, tree: BaseTree, document_path: str):
        self._tree = tree
        self._diagnostics: List[Diagnostic] = []
        self._document_path = document_path

    def _get_repo_root_path(self):
        raise NotImplementedError()

    def _add_diagnostic(
            self,
            node: YamlNode,
            message: str = "",
            diag_severity: DiagnosticSeverity = None):
        self._diagnostics.append(
            Diagnostic(
                range=Range(
                    start=Position(line=node.start_pos[0], character=node.start_pos[1]),
                    end=Position(line=node.end_pos[0], character=node.end_pos[1]),
                ),
                message=message,
                severity=diag_severity
            ))

    def _validate_no_duplicates_in_inputs(self):
        if hasattr(self._tree, 'inputs_node') and self._tree.inputs_node:
            message = "Multiple declarations of input '{}'"

            inputs_names_list = [input.key.text for input in self._tree.inputs_node.nodes]
            for input_node in self._tree.inputs_node.nodes:
                if inputs_names_list.count(input_node.key.text) > 1:
                    self._add_diagnostic(
                        input_node.key,
                        message=message.format(input_node.key.text)
                    )

    def _validate_no_duplicates_in_outputs(self):
        if hasattr(self._tree, 'outputs') and self._tree.outputs:
            message = "Multiple declarations of output '{}'. Outputs are not case sensitive."

            outputs_names_list = [output.text.lower() for output in self._tree.outputs.nodes]
            for output_node in self._tree.outputs.nodes:
                if outputs_names_list.count(output_node.text.lower()) > 1:
                    self._add_diagnostic(
                        output_node,
                        message=message.format(output_node.text)
                    )

    def validate(self):
        # errors
        self._validate_no_duplicates_in_inputs()
        self._validate_no_duplicates_in_outputs()

        return self._diagnostics
