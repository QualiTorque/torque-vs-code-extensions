import re
from typing import List, Tuple

from pygls.lsp.types.basic_structures import (
    Diagnostic,
    DiagnosticSeverity,
    Position,
    Range,
)
from pygls.workspace import Document
from server.ats.trees.common import BaseTree, YamlNode


class ValidationHandler:
    def __init__(self, tree: BaseTree, document: Document) -> None:
        self._tree = tree
        self._diagnostics: List[Diagnostic] = []
        self._document = document

    def _add_diagnostic(
        self,
        node: YamlNode = None,
        start_pos: Tuple[int, int] = None,
        end_pos: Tuple[int, int] = None,
        message: str = "",
        diag_severity: DiagnosticSeverity = None,
    ):
        if node is None and not all([start_pos, end_pos]):
            raise ValueError("Neither node object nor position tuples were provided")

        if node is not None:
            start = {
                "line": node.start_pos[0],
                "character": node.start_pos[1]
            }
            end = {
                "line": node.end_pos[0],
                "character": node.end_pos[1]
            }
        elif len(start_pos) == 2 and len(end_pos) == 2:
            start = {
                "line": start_pos[0],
                "character": start_pos[1]
            }
            end = {
                "line": end_pos[0],
                "character": end_pos[1]
            }
        else:
            raise ValueError

        range = Range(start=Position(**start), end=Position(**end))

        self._diagnostics.append(
            Diagnostic(
                    range=range,
                    message=message,
                    severity=diag_severity,
                )
            )

    def _validate_no_duplicates_in_inputs(self):
        message = "Multiple declarations of input '{}'"

        inputs_names_list = [input.key.text for input in self._tree.get_inputs()]
        for input_node in self._tree.get_inputs():
            if inputs_names_list.count(input_node.key.text) > 1:
                self._add_diagnostic(
                    input_node.key, message=message.format(input_node.key.text)
                )

    def _validate_no_reserved_words_in_inputs_prefix(self):
        message = "input '{}' contains a reserved word '{}'"
        reserved_words = ["colony", "torque"]

        for input_node in self._tree.get_inputs():
            for reserved in reserved_words:
                if input_node.key.text.lower().startswith(reserved):
                    self._add_diagnostic(
                        input_node.key,
                        message=message.format(input_node.key.text, reserved),
                    )

    def _validate_no_duplicates_in_outputs(self):
        if hasattr(self._tree, "outputs"):
            message = (
                "Multiple declarations of output '{}'. Outputs are not case sensitive."
            )

            outputs_names_list = [
                output.text.lower() for output in self._tree.get_outputs()
            ]
            for output_node in self._tree.get_outputs():
                if outputs_names_list.count(output_node.text.lower()) > 1:
                    self._add_diagnostic(
                        output_node, message=message.format(output_node.text)
                    )

    def _check_for_deprecated_properties(self, deprecated_properties):
        message_dep = "Deprecated property '{}'."
        message_replace = "Please use '{}' instead."
        line_num = 0
        for line in self._document.lines:
            for prop in deprecated_properties.keys():
                found = re.findall("^[^#\\n]*(\\b" + prop + "\\b:)", line)
                if len(found) > 0:
                    col = line.find(prop)
                    message = message_dep.format(prop)
                    if deprecated_properties[prop]:
                        message += " " + message_replace.format(
                            deprecated_properties[prop]
                        )
                    self._add_diagnostic(
                        message=message,
                        start_pos=(line_num, col),
                        end_pos=(line_num, col + len(prop)),
                        diag_severity=DiagnosticSeverity.Warning,
                    )
            line_num += 1

    def validate(self):
        # errors
        self._validate_no_duplicates_in_inputs()
        self._validate_no_duplicates_in_outputs()
        self._validate_no_reserved_words_in_inputs_prefix()

        return self._diagnostics
