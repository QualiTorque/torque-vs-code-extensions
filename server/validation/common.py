from typing import List
from pygls.lsp.types.basic_structures import Diagnostic, DiagnosticSeverity, Position, Range
from pygls.workspace import Document
from ..ats.trees.common import BaseTree, YamlNode


class ValidationHandler:
    def __init__(self, tree: BaseTree, document: Document) -> None:
        self._tree = tree
        self._diagnostics: List[Diagnostic] = []
        self._document = document

    def _add_diagnostic(
            self,
            node: YamlNode,
            message: str = "",
            diag_severity: DiagnosticSeverity = None):
        if node:
            self._diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=node.start_pos[0], character=node.start_pos[1]),
                        end=Position(line=node.end_pos[0], character=node.end_pos[1]),
                    ),
                    message=message,
                    severity=diag_severity
                ))
    
    def _add_diagnostic_for_range(
            self,
            message: str = "",
            range_start_tuple=None,
            range_end_tuple=None,
            diag_severity: DiagnosticSeverity = None):
        if range_start_tuple and range_end_tuple:
            self._diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=range_start_tuple[0], character=range_start_tuple[1]),
                        end=Position(line=range_end_tuple[0], character=range_end_tuple[1]),
                    ),
                    message=message,
                    severity=diag_severity
                ))

    def _validate_no_duplicates_in_inputs(self):
        message = "Multiple declarations of input '{}'"

        inputs_names_list = [input.key.text for input in self._tree.get_inputs()]
        for input_node in self._tree.get_inputs():
            if inputs_names_list.count(input_node.key.text) > 1:
                self._add_diagnostic(
                    input_node.key,
                    message=message.format(input_node.key.text)
                )
    
    def _validate_no_reserved_words_in_inputs_prefix(self):
        message = "input '{}' contains a reserved word '{}'"
        reserved_words = ["colony", "torque"]

        for input_node in self._tree.get_inputs():
            for reserved in reserved_words:
                if input_node.key.text.lower().startswith(reserved):
                    self._add_diagnostic(
                        input_node.key,
                        message=message.format(input_node.key.text, reserved)
                    )

    def _validate_no_duplicates_in_outputs(self):
        if hasattr(self._tree, 'outputs'):
            message = "Multiple declarations of output '{}'. Outputs are not case sensitive."

            outputs_names_list = [output.text.lower() for output in self._tree.get_outputs()]
            for output_node in self._tree.get_outputs():
                if outputs_names_list.count(output_node.text.lower()) > 1:
                    self._add_diagnostic(
                        output_node,
                        message=message.format(output_node.text)
                    )

    def validate(self):
        # errors
        self._validate_no_duplicates_in_inputs()
        self._validate_no_duplicates_in_outputs()
        self._validate_no_reserved_words_in_inputs_prefix()

        return self._diagnostics
