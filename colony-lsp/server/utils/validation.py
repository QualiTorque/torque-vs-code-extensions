import os
import re
from typing import List
from pygls.lsp.types import diagnostics
from pygls.lsp.types.basic_structures import Diagnostic, DiagnosticSeverity, Position, Range
from server.ats.tree import BlueprintTree
from server.constants import PREDEFINED_COLONY_INPUTS


class VaidationHandler:
    def __init__(self, tree: BlueprintTree, root_path: str):
        self._tree = tree
        self._diagnostics = []
        self._root_path = root_path

    def _add_diagnostic(
        self,
        start_position: Position,
        end_position: Position,
        message: str = "",
        diag_severity: DiagnosticSeverity = None):

        self._diagnostics.append(
            Diagnostic(
                range=Range(
                    start=start_position,
                    end=end_position
                ),
                message=message,
                severity=diag_severity
            ))

    def validate(self):
        pass


class BlueprintValidationHandler(VaidationHandler):
    def _validate_dependency_exists(self):
        message = "The app '{}' is not part of the blueprint applications section"
        apps = [app.name for app in self._tree.apps_node.apps]

        for app in self._tree.apps_node.apps:
            for name, node in app.depends_on.items():
                if name not in apps:
                    self._add_diagnostic(
                        Position(line=node.start[0], character=node.start[1]),
                        Position(line=node.end[0], character=node.end[1]),
                        message=message.format(name)
                    )
    
    def _validate_non_existing_app_is_declared(self):
        message = "The app '{}' could not be found in the /applications folder"
        
        diagnostics: List[Diagnostic] = []

        for app in self._tree.apps_node.apps:
            app_path = os.path.join(self._root_path, "applications", app.name, "{}.yaml".format(app.name))

            if not os.path.isfile(app_path):
                self._add_diagnostic(
                    Position(line=app.start[0], character=app.start[1]),
                    Position(line=app.start[0], character=app.start[1] + len(app.name)),
                    message=message.format(app.name)
                )


    def _check_for_unused_bluerprint_inputs(self): 
        
        used_vars = set()
        for app in self._tree.apps_node.apps:
            used_vars.update({var.value.replace("$", "") for var in app.inputs_node.inputs})

        message = "Unused variable {}"

        for input in self._tree.inputs_node.inputs:
            if input.name not in used_vars:
                self._add_diagnostic(
                    Position(line=input.start[0], character=input.start[1]),
                    Position(line=input.start[0], character=input.start[1] + len(input.name)),
                    message=message.format(input.name),
                    diag_severity=DiagnosticSeverity.Warning
                )

    def _is_valid_auto_var(self, var_name):
        if var_name.lower() in PREDEFINED_COLONY_INPUTS:
            return True, ""
        
        parts = var_name.split('.')
        if not parts[0].lower() == "$colony":
            return False, f"{var_name} is not a valid colony-generated variable"
        
        if not parts[1].lower() == "applications" and not parts[1].lower() == "services":
            return False, f"{var_name} is not a valid colony-generated variable"
        
        if len(parts) == 4: 
            if not parts[3] == "dns":
                return False, f"{var_name} is not a valid colony-generated variable"
            else:
                return True, ""
        
        if len(parts) == 5:
            if parts[1].lower() == "applications" and (not parts[3].lower() == "outputs" and 
                                                       not parts[3].lower() == "dns"):
                return False, f"{var_name} is not a valid colony-generated variable"
            
            if parts[1].lower() == "services" and not parts[3].lower() == "outputs":
                return False, f"{var_name} is not a valid colony-generated variable"
            
            if parts[1] == "applications":
                apps = [app.name for app in self._tree.apps_node.apps]
                if not parts[2] in apps:
                    return False, f"{var_name} is not a valid colony-generated variable (no such app in the blueprint)"
                #TODO: check that the app has this output
            
            #TODO: check that services exist in the blueprint, and has the output
        else:
            return False, f"{var_name} is not a valid colony-generated variable (too many parts)"
        
        return True, ""
        
    def _validate_var_being_used_is_defined(self):
        bp_inputs = {input.name for input in self._tree.inputs_node.inputs}
        message = "Variable '{}' is not defined"
        regex = re.compile('(^\$.+?$|\$\{.+?\})')
        for app in self._tree.apps_node.apps:
            for input in app.inputs_node.inputs:
                # we need to check values starting with '$' 
                # and they shouldnt be colony related
                
                # need to break value to parts to handle variables in {} like: 
                # abcd/${some_var}/asfsd/${var2}
                # and highlight these portions      
                iterator = regex.finditer(input.value)
                for match in iterator:
                    cur_var = match.group()
                    pos = match.span()
                    if cur_var.startswith("${") and cur_var.endswith("}"):
                        cur_var = "$" + cur_var[2:-1]
            
                    if cur_var.startswith("$") and "." not in cur_var:
                        var = cur_var.replace("$", "")
                        if var not in bp_inputs:
                            self._add_diagnostic(
                                Position(line=input.start[0], character=input.start[1]+pos[0]),
                                Position(line=input.start[0], character=input.start[1]+pos[1]),
                                message=message.format(input.value)
                            )
                    elif cur_var.lower().startswith("$colony"):
                        print("colony var")
                        valid_var, error_message = self._is_valid_auto_var(cur_var)
                        if not valid_var:
                            self._add_diagnostic(
                                    Position(line=input.start[0], character=input.start[1]+pos[0]),
                                    Position(line=input.start[0], character=input.start[1]+pos[1]),
                                    message=error_message
                            )
                    
    def validate(self):
        # warnings
        self._check_for_unused_bluerprint_inputs()
        # errors
        self._validate_dependency_exists()
        self._validate_var_being_used_is_defined()
        self._validate_non_existing_app_is_declared()
        return self._diagnostics
