import os
from typing import List
from pygls.lsp.types import diagnostics
from pygls.lsp.types.basic_structures import Diagnostic, Position, Range
from server.ats.tree import BlueprintTree


class BlueprintValidationHandler:
    # TODO: refactor to have a single validate function 
    def __init__(self, tree: BlueprintTree):
        self._tree = tree
        self._diagnostics = []

    def _validate_dependency_exists(self):
        message = "This app is not declared: {}"
        apps = [app.name for app in self._tree.apps_node.apps]

        for app in self._tree.apps_node.apps:
            for name, node in app.depends_on.items():
                if name not in apps:
                    self._diagnostics.append(diagnostics(
                        range=Range(
                            start=Position(line=node.start[0], character=node.start[1]),
                            end=Position(line=node.end[0], character=node.end[1]),
                        ),
                        message=message.format(name)
                    ))

    def validate_non_existing_app_is_declared(self, root_path: str):
        message = "This app does not exist in blueprint repo: {}"
        
        diagnostics: List[Diagnostic] = []

        for app in self._tree.apps_node.apps:
            app_path = os.path.join(root_path, "applications", app.name, "{}.yaml".format(app.name))

            if not os.path.isfile(app_path):
                diagnostics.append(Diagnostic(
                    range=Range(
                        start=Position(line=app.start[0], character=app.start[1]),
                        end=Position(line=app.end[0], character=app.end[1]),
                    ),
                    message=message.format(app.name)
                ))
        
        return diagnostics

    def _validate_unused_bluerprint_inputs(self): # TODO: must work with tree only
        # bp_inputs = {input.name for input in self._tree.inputs_node.inputs}
        
        used_vars = set()
        for app in self._tree.apps_node.apps:
            used_vars.update({var.value.replace("$", "") for var in app.inputs_node.inputs})

        message = "Unused variable {}"

        for input in self._tree.inputs_node.inputs:
            if input.name not in used_vars:
                self._diagnostics.append(Diagnostic(
                    range=Range(
                        start=Position(line=input.start[0], character=input.start[1]),
                        end=Position(line=input.start[0], character=input.start[1] + len(input.name))
                    ),
                    message=message.format(input.name)
                ))

    def _validate_var_being_used_is_defined(self):
        bp_inputs = {input.name for input in self._tree.inputs_node.inputs}
        message = "Variable '{}' is not defined"
        for app in self._tree.apps_node.apps:
            for input in app.inputs_node.inputs:
                # we need to check values starting with '$' 
                # and they shouldnt be colony related
                if input.value.startswith("$") and "." not in input.value:
                    var = input.value.replace("$", "")
                    if var not in bp_inputs:
                        self._diagnostics.append(Diagnostic(
                            range=Range(
                                start=Position(line=input.start[0], character=input.start[1]),
                                end=Position(line=input.end[0], character=input.end[1])
                            ),
                            message=message.format(input.value)
                        ))

    def validate(self):
        self._validate_dependency_exists()
        self._validate_unused_bluerprint_inputs()
        self._validate_var_being_used_is_defined()
        return self._diagnostics
