import os
import re
import sys
import logging
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
        if hasattr(self._tree, 'inputs_node') and self._tree.inputs_node:
            message = "Multiple declarations of input '{}'"

            inputs_names_list = [input.key.text for input in self._tree.inputs_node.inputs]
            for input_node in self._tree.inputs_node.inputs:
                if inputs_names_list.count(input_node.key.text) > 1:
                    self._add_diagnostic(
                        input_node.key,
                        message=message.format(input_node.key.text)
                    )
    
    def _validate_no_duplicates_in_outputs(self):
        if hasattr(self._tree, 'outputs') and self._tree.outputs:
            message = "Multiple declarations of output '{}'. Outputs are not case sensitive."

            outputs_names_list = [output.text.lower() for output in self._tree.outputs]
            for output_node in self._tree.outputs:
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


class AppValidationHandler(ValidationHandler):
    def validate_script_files_exist(self):
        # TODO: move the code from server.py to here after having the configuration tree ready
        pass
    
    def validate(self):
        super().validate()
        #errors
        self.validate_script_files_exist()
        
        return self._diagnostics
    
class ServiceValidationHandler(ValidationHandler):
    def validate(self):
        super().validate()
        
        return self._diagnostics

class BlueprintValidationHandler(ValidationHandler):
    def __init__(self, tree: BlueprintTree, root_path: str):
        super().__init__(tree, root_path)
        self.blueprint_apps = [app.id.text for app in self._tree.apps_node.nodes] if self._tree.apps_node else []
        self.blueprint_services = [srv.id.text for srv in self._tree.services_node.nodes] if self._tree.services_node else []
    
    def _check_for_deprecated_properties(self, text_doc):
        deprecated_properties = {"availability": "bastion_availability"}
        message = "Deprecated property '{}'. Please use '{}' instead."
        line_num = 0
        for line in text_doc.lines:
            for prop in deprecated_properties.keys():
                found = re.findall('^(?!.*#).*(\\b'+prop+'\\b:)', line)
                if len(found) > 0:
                    col = line.find(prop)
                    self._diagnostics.append(
                        Diagnostic(
                            range=Range(
                                start=Position(line=line_num, character=col),
                                end=Position(line=line_num, character=col+len(prop)),
                            ),
                            message=message.format(prop, deprecated_properties[prop]),
                            severity=DiagnosticSeverity.Warning
                    ))
            line_num += 1
    
    def _check_for_deprecated_syntax(self, text_doc):
        deprecated_syntax = {
            "outputs\..+": "colony.[app_name|service_name].outputs.[output_name]", 
            "colony.sandboxid": "colony.environment.id"
                            }
        message = "Deprecated syntax '{}'. Please use '{}' instead."
        line_num = 0
        for line in text_doc.lines:
            for prop in deprecated_syntax.keys():
                for match in re.finditer('^(?!.*#).*(\$\{'+prop+'?\}|\$'+prop+'\\b)', line.lower()):
                    col = match.span(1)
                    old_syntax = match.group(1).replace('$', '').replace('{', '').replace('}', '')
                    self._diagnostics.append(
                        Diagnostic(
                            range=Range(
                                start=Position(line=line_num, character=col[0]),
                                end=Position(line=line_num, character=col[1]),
                            ),
                            message=message.format(old_syntax, deprecated_syntax[prop]),
                            severity=DiagnosticSeverity.Warning
                    ))
                    
            line_num += 1

    def _validate_dependency_exists(self):
        message = "The application/service '{}' is not defined in the applications/services section"            
        apps = self.blueprint_apps
        srvs = self.blueprint_services
        apps_n_srvs = set(apps + srvs)

        if self._tree.apps_node:
            for app in self._tree.apps_node.nodes:
                for dep in app.depends_on:
                    if dep.text not in apps_n_srvs:
                        self._add_diagnostic(dep, message=message.format(dep.text))
                    elif dep.text == app.id.text:
                        self._add_diagnostic(dep, message=f"The app '{app.id.text}' cannot be dependent of itself")
        if self._tree.services_node:
            for srv in self._tree.services_node.nodes:
                for dep in srv.depends_on:
                    if dep.text not in apps_n_srvs:
                        self._add_diagnostic(dep, message=message.format(dep.text))
                    elif dep.text == srv.id.text:
                        self._add_diagnostic(dep, message=f"The service '{srv.id.text}' cannot be dependent of itself")

    def _validate_non_existing_app_is_used(self):
        if self._tree.apps_node:
            message = "The app '{}' could not be found in the /applications folder"
            available_apps = applications.get_available_applications_names()
            for app in self._tree.apps_node.nodes:
                if app.id.text not in available_apps:
                    self._add_diagnostic(app.id, message=message.format(app.id.text))
    
    def _validate_blueprint_apps_have_input_values(self):
        if self._tree.apps_node:
            for app in self._tree.apps_node.nodes:
                for var in app.inputs_node.inputs:
                    if not var.value:
                        self._add_diagnostic(var.key, message="Application input must have a value")
    
    def _validate_blueprint_services_have_input_values(self):
        if self._tree.services_node:
            for app in self._tree.services_node.nodes:
                for var in app.inputs_node.inputs:
                    if not var.value:
                        self._add_diagnostic(var.key, message="Service input must have a value")

    def _validate_non_existing_service_is_used(self):
        if self._tree.services_node:
            message = "The service '{}' could not be found in the /services folder"
            available_srvs = services.get_available_services_names()
            for srv in self._tree.services_node.nodes:
                if srv.id.text not in available_srvs:
                    self._add_diagnostic(srv.id, message=message.format(srv.id.text))

    def _check_for_unused_blueprint_inputs(self, text_doc):
        if hasattr(self._tree, 'inputs_node') and self._tree.inputs_node:
            message = "Unused variable {}"
            source = text_doc.source
            for input in self._tree.inputs_node.inputs:
                found = re.findall('^(?!.*#).*(\$\{'+input.key.text+'\}|\$'+input.key.text+'\\b)', source, re.MULTILINE)
                if len(found) == 0:
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
        bp_inputs = {input.key.text for input in self._tree.inputs_node.inputs} if hasattr(self._tree, 'inputs_node') and self._tree.inputs_node else {}
        if self._tree.apps_node:
            for app in self._tree.apps_node.nodes:
                for input in app.inputs_node.inputs:
                    self._confirm_variable_defined_in_blueprint_or_auto_var(bp_inputs, input)
        
        if self._tree.services_node:
            for srv in self._tree.services_node.nodes:
                for input in srv.inputs_node.inputs:
                    self._confirm_variable_defined_in_blueprint_or_auto_var(bp_inputs, input)
        
        if self._tree.artifacts:
            for art in self._tree.artifacts:
                self._confirm_variable_defined_in_blueprint_or_auto_var(bp_inputs, art)

    def _confirm_variable_defined_in_blueprint_or_auto_var(self, bp_inputs, input):
        # need to break value to parts to handle variables in {} like: 
        # abcd/${some_var}/asfsd/${var2}
        # and highlight these portions      
        message = "Variable '{}' is not defined"
        regex = re.compile('(\$\{.+?\}|^\$.+?$)')
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
        if self._tree.apps_node:
            for app in self._tree.apps_node.nodes:
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
        if self._tree.services_node:
            for srv in self._tree.services_node.nodes:
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
        if self._tree.artifacts:
            for art in self._tree.artifacts:
                if art.key.text not in self.blueprint_apps:
                    self._add_diagnostic(art.key, message="This application is not defined in this blueprint.")
    
    def _validate_artifaces_are_unique(self):
        if self._tree.artifacts:
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
        if self._tree.apps_node:
            apps = applications.get_available_applications_names()
            for app in self._tree.apps_node.nodes:
                if app.id.text in apps:
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
        if self._tree.services_node:
            srvs = services.get_available_services_names()
            for srv in self._tree.services_node.nodes:
                if srv.id.text in srvs:
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
     
    def validate(self, text_doc):
        super().validate()

        try:
            # prep
            _ = applications.get_available_applications(self._root_path)
            _ = services.get_available_services(self._root_path)
            # warnings
            self._check_for_unused_blueprint_inputs(text_doc)
            self._check_for_deprecated_properties(text_doc)
            self._check_for_deprecated_syntax(text_doc)
            # errors
            self._validate_blueprint_apps_have_input_values()
            self._validate_blueprint_services_have_input_values()
            self._validate_dependency_exists()
            self._validate_var_being_used_is_defined()
            self._validate_non_existing_app_is_used()
            self._validate_non_existing_service_is_used()
            self._validate_apps_and_services_are_unique()
            self._validate_artifaces_apps_are_defined()
            self._validate_artifaces_are_unique()
            self._validate_apps_inputs_exists()
            self._validate_services_inputs_exists()
        except Exception as ex:
            print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
                
        return self._diagnostics
