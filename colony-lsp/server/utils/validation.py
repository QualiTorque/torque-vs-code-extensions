import os
import re
from typing import List
from pygls.lsp.types import diagnostics
from pygls.lsp.types.basic_structures import Diagnostic, DiagnosticSeverity, Position, Range
from server.ats.tree import BaseTree, BlueprintTree, YamlNode
from server.constants import PREDEFINED_COLONY_INPUTS
from server.utils import applications, services


class ValidationHandler:
    def __init__(self, tree: BaseTree, root_path: str):
        self._tree = tree
        self._diagnostics: List[Diagnostic] = []
        self._root_path = root_path

    def _add_diagnostic(
            self,
            node: YamlNode,
            message: str = "",
            diag_severity: DiagnosticSeverity = None):
        self._diagnostics.append(
            Diagnostic(
                range=Range(
                    start=Position(line=node.start[0], character=node.start[1]),
                    end=Position(line=node.end[0], character=node.end[1]),
                ),
                message=message,
                severity=diag_severity
            ))

    def _validate_no_duplicates_in_inputs(self):
        message = "Multiple declaration of input '{}'"

        inputs_names_list = [input.key.text for input in self._tree.inputs_node.inputs]

        for input_node in self._tree.inputs_node.inputs:
            if inputs_names_list.count(input_node.key.text) > 1:
                self._add_diagnostic(
                    Position(line=input_node.key.start[0], character=input_node.key.start[1]),
                    Position(line=input_node.key.end[0], character=input_node.key.end[1]),
                    message=message.format(input_node.key.text)
                )

    def validate(self):
        # errors
        self._validate_no_duplicates_in_inputs()

        return self._diagnostics


class AppValidationHandler(ValidationHandler):
    pass


class BlueprintValidationHandler(ValidationHandler):
    def __init__(self, tree: BlueprintTree, root_path: str):
        super().__init__(tree, root_path)
        self.blueprint_apps = [app.id.text for app in self._tree.apps_node.items] if self._tree.apps_node else []
        self.blueprint_services = [srv.id.text for srv in self._tree.services_node.items] if self._tree.services_node else []

    def _validate_dependency_exists(self):
        message = "The application/service '{}' is not defined in the applications/services section"            
        apps = self.blueprint_apps
        srvs = self.blueprint_services
        apps_n_srvs = set(apps + srvs)

        if self._tree.apps_node:
            for app in self._tree.apps_node.items:
                for dep in app.depends_on:
                    if dep.text not in apps_n_srvs:
                        self._add_diagnostic(dep, message=message.format(dep.text))
                    elif dep.text == app.id.text:
                        self._add_diagnostic(dep, message=f"The app '{app.id.text}' cannot be dependent of itself")
        if self._tree.services_node:
            for srv in self._tree.services_node.items:
                for dep in srv.depends_on:
                    if dep.text not in apps_n_srvs:
                        self._add_diagnostic(dep, message=message.format(dep.text))
                    elif dep.text == srv.id.text:
                        self._add_diagnostic(dep, message=f"The service '{srv.id.text}' cannot be dependent of itself")

    def _validate_non_existing_app_is_used(self):
        message = "The app '{}' could not be found in the /applications folder"
        available_apps = applications.get_available_applications_names()
        for app in self._tree.apps_node.items:
            if app.id.text not in available_apps:
                self._add_diagnostic(app.id, message=message.format(app.id.text))

    def _validate_non_existing_service_is_used(self):
        message = "The service '{}' could not be found in the /services folder"
        available_srvs = services.get_available_services_names()
        for srv in self._tree.services_node.items:
            if srv.id.text not in available_srvs:
                self._add_diagnostic(srv.id, message=message.format(srv.id.text))

    def _check_for_unused_blueprint_inputs(self):
        used_vars = set()
        for app in self._tree.apps_node.items:
            used_vars.update({var.value.text.replace("$", "") for var in app.inputs_node.inputs})
        for srv in self._tree.services_node.items:
            used_vars.update({var.value.text.replace("$", "") for var in srv.inputs_node.inputs})
        for art in self._tree.artifacts:
            if art.value:
                used_vars.add(art.value.text.replace("$", ""))

        message = "Unused variable {}"

        for input in self._tree.inputs_node.inputs:
            if input.key.text not in used_vars:
                self._add_diagnostic(
                    input.key,
                    message=message.format(input.key.text),
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
                apps = self.blueprint_apps
                if not parts[2] in apps:
                    return False, f"{var_name} is not a valid colony-generated variable (no such app in the blueprint)"
                
                # TODO: check that the app is in the depends_on section

                app_outputs = applications.get_app_outputs(app_name=parts[2])
                if parts[4] not in app_outputs:
                    return False, f"{var_name} is not a valid colony-generated variable ('{parts[2]}' does not have the output '{parts[4]}')"

            if parts[1] == "services":
                srvs = self.blueprint_services
                if not parts[2] in srvs:
                    return False, f"{var_name} is not a valid colony-generated variable (no such service in the blueprint)"

                # TODO: check that the service is in the depends_on section
                
                srv_outputs = services.get_service_outputs(srv_name=parts[2])
                if parts[4] not in srv_outputs:
                    return False, f"{var_name} is not a valid colony-generated variable ('{parts[2]}' does not have the output '{parts[4]}')"

        else:
            return False, f"{var_name} is not a valid colony-generated variable (too many parts)"

        return True, ""

    def _validate_var_being_used_is_defined(self):
        bp_inputs = {input.key.text for input in self._tree.inputs_node.inputs}
        for app in self._tree.apps_node.items:
            for input in app.inputs_node.inputs:
                self._confirm_variable_defined_in_blueprint_or_auto_var(bp_inputs, input)
        
        for srv in self._tree.services_node.items:
            for input in srv.inputs_node.inputs:
                self._confirm_variable_defined_in_blueprint_or_auto_var(bp_inputs, input)
        
        for art in self._tree.artifacts:
            self._confirm_variable_defined_in_blueprint_or_auto_var(bp_inputs, art)

    def _confirm_variable_defined_in_blueprint_or_auto_var(self, bp_inputs, input):
        # need to break value to parts to handle variables in {} like: 
        # abcd/${some_var}/asfsd/${var2}
        # and highlight these portions      
        message = "Variable '{}' is not defined"
        regex = re.compile('(^\$.+?$|\$\{.+?\})')
        try:
            if input.value:
                iterator = regex.finditer(input.value.text)
                for match in iterator:
                    cur_var = match.group()
                    pos = match.span()
                    if cur_var.startswith("${") and cur_var.endswith("}"):
                        cur_var = "$" + cur_var[2:-1]

                    if cur_var.startswith("$") and "." not in cur_var:
                        var = cur_var.replace("$", "")
                        if var not in bp_inputs:
                            self._diagnostics.append(Diagnostic(
                                range=Range(
                                    start=Position(line=input.value.start[0], character=input.value.start[1] + pos[0]),
                                    end=Position(line=input.value.end[0], character=input.value.start[1] + pos[1]),
                                ),
                                message=message.format(cur_var),
                            ))
                    elif cur_var.lower().startswith("$colony"):
                        valid_var, error_message = self._is_valid_auto_var(cur_var)
                        if not valid_var:
                            self._diagnostics.append(Diagnostic(
                                range=Range(
                                    start=Position(line=input.value.start[0], character=input.value.start[1] + pos[0]),
                                    end=Position(line=input.value.end[0], character=input.value.start[1] + pos[1]),
                                ),
                                message=error_message
                            ))
        except Exception as ex:
            print(ex)

    def _validate_apps_and_services_are_unique(self):
        # check that there are no duplicate names in the apps being used
        duplicated = {}
        apps = {}
        for app in self._tree.apps_node.items:
            if app.id.text not in apps:
                apps[app.id.text] = app
            else:
                msg = "This application is already defined. Each application should be defined only once."
                self._add_diagnostic(app.id, message=msg)

                if app.id.text not in duplicated:
                    prev_app = apps[app.id.text]
                    self._add_diagnostic(prev_app.id, message=msg)
                    duplicated[app.id.text] = 1
            
        # check that there are no duplicate names in the services being used
        srvs = {}
        for srv in self._tree.services_node.items:
            if srv.id.text not in srvs:
                srvs[srv.id.text] = srv
            else:
                msg = "This service is already defined. Each service should be defined only once."
                self._add_diagnostic(srv.id, message=msg)

                if srv.id.text not in duplicated:
                    prev_srv = srvs[srv.id.text]
                    self._add_diagnostic(prev_srv.id, message=msg)
                    duplicated[srv.id.text] = 1
            
            # check that there is no app with this name
            if srv.id.text in apps:
                msg = "There is already an application with the same name in this blueprint. Make sure the names are unique."
                self._add_diagnostic(srv.id, message=msg)

                prev_app = apps[srv.id.text]
                self._add_diagnostic(prev_app.id, message=msg)
    
    def _validate_artifaces_apps_are_defined(self):
        for art in self._tree.artifacts:
            if art.key.text not in self.blueprint_apps:
                self._add_diagnostic(art.key, message="This application is not defined in this blueprint.")
    
    def _validate_artifaces_are_unique(self):
        arts = {}
        duplicated = {}
        msg = "This artifact is already defined. Each artifact should be defined only once."
        for art in self._tree.artifacts:
            if art.key.text not in arts:
                arts[art.key.text] = art
            else:
                self._add_diagnostic(art.key, message=msg)

                if art.key.text not in duplicated:
                    prev_art = arts[art.key.text]
                    self._add_diagnostic(prev_art.key, message=msg)
                    duplicated[prev_art.key.text] = 1
    
    def _validate_apps_inputs_exists(self):
        for app in self._tree.apps_node.items:
            app_inputs = applications.get_app_inputs(app.id.text)
            used_inputs = []
            for input in app.inputs_node.inputs:
                used_inputs.append(input.key.text)
                if input.key.text not in app_inputs:
                    self._add_diagnostic(
                        input.key,
                        message=f"The application '{app.id.text}' does not have an input named '{input.key.text}'"
                    )
            missing_inputs = []
            for input in app_inputs:
                if app_inputs[input] is None and input not in used_inputs:
                    missing_inputs.append(input)
            if missing_inputs:
                self._add_diagnostic(
                    app.id,
                    message=f"The following mandatory inputs are missing: {', '.join(missing_inputs)}"
                )
            
    def _validate_services_inputs_exists(self):
        for srv in self._tree.services_node.items:
            srv_inputs = services.get_service_inputs(srv.id.text)
            used_inputs = []
            for input in srv.inputs_node.inputs:
                used_inputs.append(input.key.text)
                if input.key.text not in srv_inputs:
                    self._add_diagnostic(
                        input.key,
                        message=f"The service '{srv.id.text}' does not have an input named '{input.key.text}'"
                    )
            missing_inputs = []
            for input in srv_inputs:
                if srv_inputs[input] is None and input not in used_inputs:
                    missing_inputs.append(input)
            if missing_inputs:
                self._add_diagnostic(
                    srv.id,
                    message=f"The following mandatory inputs are missing: {', '.join(missing_inputs)}"
                )
     
    def validate(self):
        super().validate()

        # prep
        _ = applications.get_available_applications(self._root_path)
        _ = services.get_available_services(self._root_path)
        # warnings
        self._check_for_unused_blueprint_inputs()
        # errors
        self._validate_dependency_exists()
        self._validate_var_being_used_is_defined()
        self._validate_non_existing_app_is_used()
        self._validate_non_existing_service_is_used()
        self._validate_apps_and_services_are_unique()
        self._validate_artifaces_apps_are_defined()
        self._validate_artifaces_are_unique()
        self._validate_apps_inputs_exists()
        self._validate_services_inputs_exists()
        return self._diagnostics
