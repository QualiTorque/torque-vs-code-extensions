
import pathlib
import re
from server.validation.common import ValidationHandler
import sys
import logging
from pygls.lsp.types.basic_structures import Diagnostic, DiagnosticSeverity, Position, Range
from server.ats.trees.blueprint import BlueprintTree
from server.constants import PREDEFINED_COLONY_INPUTS
from server.utils import applications, services


class BlueprintValidationHandler(ValidationHandler):
    def __init__(self, tree: BlueprintTree, document_path: str):
        super().__init__(tree, document_path)
        self.blueprint_apps = [app.id.text for app in self._tree.applications.nodes] if self._tree.applications else []
        self.blueprint_services = [srv.id.text for srv in self._tree.services.nodes] if self._tree.services else []

    def _get_repo_root_path(self):
        path = pathlib.Path(self._document.path).absolute()
        if path.parents[0].name == "blueprints":
            return path.parents[1].absolute().as_posix()

        else:
            raise ValueError(f"Wrong document path of blueprint file: {path.as_posix()}")    

    def _check_for_deprecated_properties(self):
        deprecated_properties = {"availability": "bastion_availability",
                                 "environmentType": None}
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

    def _check_for_deprecated_syntax(self):
        deprecated_syntax = {
            "outputs\..+": "colony.[app_name|service_name].outputs.[output_name]",
            "colony.sandboxid": "colony.environment.id",
            "colony.publicaddress": "colony.environment.public_address",
            "colony.virtualnetworkid": "colony.environment.virtual_network_id"
                            }
        message = "Deprecated syntax '{}'. Please use '{}' instead."
        line_num = 0
        for line in self._document.lines:
            for prop in deprecated_syntax.keys():
                for match in re.finditer('^[^#\\n]*(\$\{'+prop+'?\}|\$'+prop+'\\b)', line.lower()):
                    col = match.span(1)
                    old_syntax = match.group(1).replace('$', '').replace('{', '').replace('}', '')
                    self._add_diagnostic_for_range(message.format(old_syntax, deprecated_syntax[prop]),
                                                   range_start_tupple=(line_num, col[0]),
                                                   range_end_tupple=(line_num, col[1]),
                                                   diag_severity=DiagnosticSeverity.Warning)

            line_num += 1

    def _validate_dependency_exists(self):
        message = "The application/service '{}' is not defined in the applications/services section"
        apps = self.blueprint_apps
        srvs = self.blueprint_services
        apps_n_srvs = set(apps + srvs)

        tree_apps = self._tree.get_applications()
            
        for app in tree_apps:
            deps = app.depends_on
            
            for dep in deps:
                if dep.text not in apps_n_srvs:
                    self._add_diagnostic(dep, message=message.format(dep.text))
                elif dep.text == app.id.text:
                    self._add_diagnostic(dep, message=f"The app '{app.id.text}' cannot be dependent of itself")

        tree_srvs = self._tree.get_services()
        
        for srv in tree_srvs:
            deps = srv.depends_on

            for dep in srv.details.depends_on.nodes:
                if dep.text not in apps_n_srvs:
                    self._add_diagnostic(dep, message=message.format(dep.text))
                elif dep.text == srv.id.text:
                    self._add_diagnostic(dep, message=f"The service '{srv.id.text}' cannot be dependent of itself")

    def _validate_non_existing_app_is_used(self):
        if self._tree.applications:
            message = "The app '{}' could not be found in the /applications folder"
            available_apps = applications.get_available_applications_names()
            for app in self._tree.applications.nodes:
                if app.id.text not in available_apps:
                    self._add_diagnostic(app.id, message=message.format(app.id.text))
    
    def _validate_used_apps_are_valid(self):
        if self._tree.applications:
            message = "The app '{}' is not valid. Open the file to get more details."
            available_apps = applications.get_available_applications()
            for app in self._tree.applications.nodes:
                if app.id.text in available_apps:
                    if available_apps[app.id.text]["app_tree"] is None:
                        self._add_diagnostic(app.id, message=message.format(app.id.text))
            
    def _validate_blueprint_apps_have_input_values(self):
        if self._tree.applications and self._tree.inputs_node:
            blueprint_inputs = {input.key.text: 1 for input in self._tree.inputs_node.nodes}
            for app in self._tree.applications.nodes:
                if app.value and app.value.input_values:
                    for var in app.value.input_values.nodes:
                        if not var.value and var.key.text not in blueprint_inputs:
                            self._add_diagnostic(var.key, message="Application input must have a value or a blueprint input with the same name should be defined")

    def _validate_blueprint_services_have_input_values(self):
        if self._tree.services and self._tree.inputs_node:
            blueprint_inputs = {input.key.text: 1 for input in self._tree.inputs_node.nodes}
            for srv in self._tree.services.nodes:
                if srv.value and srv.value.input_values:
                    for var in srv.value.input_values.nodes:
                        if not var.value and var.key.text not in blueprint_inputs:
                            self._add_diagnostic(var.key, message="Service input must have a value or a blueprint input with the same name should be defined")

    def _validate_non_existing_service_is_used(self):
        if self._tree.services:
            message = "The service '{}' could not be found in the /services folder"
            available_srvs = services.get_available_services_names()
            for srv in self._tree.services.nodes:
                if srv.id.text not in available_srvs:
                    self._add_diagnostic(srv.id, message=message.format(srv.id.text))
    
    def _validate_used_services_are_valid(self):
        if self._tree.services:
            message = "The service '{}' is not valid. Open the file to get more details."
            available_srvs = services.get_available_services()
            for srv in self._tree.services.nodes:
                if srv.id.text in available_srvs:
                    if available_srvs[srv.id.text]["srv_tree"] is None:
                        self._add_diagnostic(srv.id, message=message.format(srv.id.text))

    def _check_for_unused_blueprint_inputs(self):
        if self._tree.inputs_node:
            message = "Unused variable {}"
            source = self._document.source
            # build a list of inputs used as "name only" to be matched with a blueprint input
            name_only_inputs = {}
            if self._tree.applications:
                for app in self._tree.applications.nodes:
                    if app.value and app.value.input_values:
                        for var in app.value.input_values.nodes:
                            if var.value is None and var.key.text not in name_only_inputs:
                                name_only_inputs[var.key.text] = 1
            if self._tree.services:
                for srv in self._tree.services.nodes:
                    if srv.value and srv.value.input_values:
                        for var in srv.value.input_values.nodes:
                            if var.value is None and var.key.text not in name_only_inputs:
                                name_only_inputs[var.key.text] = 1
            # search if used as a variable
            for input in self._tree.inputs_node.nodes:
                if input.key.text not in name_only_inputs:
                    found = re.findall('^[^#\\n]*(\$\{'+input.key.text+'\}|\$'+input.key.text+'\\b)', source, re.MULTILINE)
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

<<<<<<< HEAD
        if not parts[1].lower() in ["applications", "services", "parameters"]:
=======
        if not parts[1].lower() in ["applications", "services", "parameters", "repos"]:
>>>>>>> develop
            return False, f"{var_name} is not a valid colony-generated variable"

        if len(parts) == 3:
            if not parts[1] == "parameters":
                return False, f"{var_name} is not a valid colony-generated variable"
            else:
                # currently no other validation for parameter store inputs
                return True, ""
        
        if len(parts) == 4:
            if parts[1] == "repos" and parts[3] not in ["token", "url"]:
                return False, f"{var_name} is not a valid colony-generated variable"
            elif parts[1] == "applications" and not parts[3] == "dns":
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
        bp_inputs = {input.key.text for input in self._tree.inputs_node.nodes} if self._tree.inputs_node else {}
        if self._tree.applications:
            for app in self._tree.applications.nodes:
                if not app.details or not app.details.input_values:
                    continue
                
                for input in app.details.input_values.nodes:
                    self._confirm_variable_defined_in_blueprint_or_auto_var(bp_inputs, input)

        if self._tree.services:
            for srv in self._tree.services.nodes:
                if not srv.details or not srv.details.input_values:
                    continue

                for input in srv.details.input_values.nodes:
                    self._confirm_variable_defined_in_blueprint_or_auto_var(bp_inputs, input)

        if self._tree.artifacts:
            for art in self._tree.artifacts.nodes:
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
                                    start=Position(line=input.value.start_pos[0],
                                                   character=input.value.start_pos[1] + pos[0]),
                                    end=Position(line=input.value.end_pos[0],
                                                 character=input.value.start_pos[1] + pos[1]),
                                ),
                                message=message.format(cur_var),
                            ))
                    elif cur_var.lower().startswith("$colony"):
                        valid_var, error_message = self._is_valid_auto_var(cur_var)
                        if not valid_var:
                            self._diagnostics.append(Diagnostic(
                                range=Range(
                                    start=Position(line=input.value.start_pos[0],
                                                   character=input.value.start_pos[1] + pos[0]),
                                    end=Position(line=input.value.end_pos[0],
                                                 character=input.value.start_pos[1] + pos[1]),
                                ),
                                message=error_message
                            ))
        except Exception as ex:
            print(ex)

    def _validate_apps_and_services_are_unique(self):
        # check that there are no duplicate names in the apps being used
        duplicated = {}
        apps = {}
        if self._tree.applications:
            for app in self._tree.applications.nodes:
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
        if self._tree.services:
            for srv in self._tree.services.nodes:
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

    def _validate_artifacts_apps_are_defined(self):
        if self._tree.artifacts:
            for art in self._tree.artifacts.nodes:
                if art.key.text not in self.blueprint_apps:
                    self._add_diagnostic(art.key, message="This application is not defined in this blueprint.")

    def _validate_artifacts_are_unique(self):
        if self._tree.artifacts:
            arts = {}
            duplicated = {}
            msg = "This artifact is already defined. Each artifact should be defined only once."
            for art in self._tree.artifacts.nodes:
                if art.key.text not in arts:
                    arts[art.key.text] = art
                else:
                    self._add_diagnostic(art.key, message=msg)

                    if art.key.text not in duplicated:
                        prev_art = arts[art.key.text]
                        self._add_diagnostic(prev_art.key, message=msg)
                        duplicated[prev_art.key.text] = 1

    def _validate_apps_inputs_exists(self):
        if self._tree.applications:
            apps = applications.get_available_applications_names()
            for app in self._tree.applications.nodes:
                if app.id.text in apps:
                    app_inputs = applications.get_app_inputs(app.id.text)
                    used_inputs = []
                    if app.details and app.details.input_values:
                        for input in app.details.input_values.nodes:    
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
        if self._tree.services:
            srvs = services.get_available_services_names()
            for srv in self._tree.services.nodes:
                if srv.id.text in srvs:
                    srv_inputs = services.get_service_inputs(srv.id.text)
                    used_inputs = []

                    if srv.details and srv.details.input_values:
                        for input in srv.details.input_values.nodes:
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

    def _validate_blueprint_networking_gateway_not_same_as_management_or_application(self):
        if self._tree.infrastructure and self._tree.infrastructure.connectivity:
            if self._tree.infrastructure.connectivity.virtual_network and self._tree.infrastructure.connectivity.virtual_network.subnets:
                subs = self._tree.infrastructure.connectivity.virtual_network.subnets
                if subs.gateway and subs.gateway.nodes and \
                   subs.management and subs.management.nodes and \
                   subs.application and subs.application.nodes:
                    gw = subs.gateway.nodes[0]
                    mgmt = subs.management.nodes[0]
                    app = subs.application.nodes[0]
                    if gw.text == mgmt.text or gw.text == app.text:
                        self._add_diagnostic(gw, message="Blueprint Gateway subnet cannot be used as management or application subnet.")
                    
                    
    # def _validate_variables_being_used_where_it_is_allowed(self, tree):
    #     tree_nodes = vars(tree)
    #     for node_name, tree_node in tree_nodes.items():
    #         if tree_node and node_name not in ['parent', 'start', 'end', 'key', 'id']:
    #             if isinstance(tree_node, MappingNode):
    #                 allow_var = tree_node.allow_variable
    #                 if item.value:
    #                     print(allow_var, item.value.text)
    #             elif isinstance(tree_node, YamlNode):
    #                 self._validate_variables_being_used_where_it_is_allowed(tree_node)
    #             elif isinstance(tree_node, List):
    #                 for item in tree_node:
    #                     if isinstance(item, MappingNode):
    #                         allow_var = item.allow_variable
    #                         if item.value:
    #                             print(allow_var, item.value.text)
    #                     else:
    #                         self._validate_variables_being_used_where_it_is_allowed(item)



    def validate(self):
        super().validate()

        try:
            # prep
            root_path = self._get_repo_root_path()

            _ = applications.get_available_applications(root_path)
            _ = services.get_available_services(root_path)
            # warnings
            self._check_for_unused_blueprint_inputs()
            self._check_for_deprecated_properties()
            self._check_for_deprecated_syntax()
            # errors
            self._validate_blueprint_apps_have_input_values()
            self._validate_blueprint_services_have_input_values()
            # self._validate_variables_being_used_where_it_is_allowed(self._tree)
            self._validate_dependency_exists()
            self._validate_var_being_used_is_defined()
            self._validate_non_existing_app_is_used()
            self._validate_non_existing_service_is_used()
            self._validate_apps_and_services_are_unique()
            self._validate_artifacts_apps_are_defined()
            self._validate_artifacts_are_unique()
            self._validate_apps_inputs_exists()
            self._validate_services_inputs_exists()
            self._validate_used_apps_are_valid()
            self._validate_used_services_are_valid()
            self._validate_blueprint_networking_gateway_not_same_as_management_or_application()
        except Exception as ex:
            print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)

        return self._diagnostics
