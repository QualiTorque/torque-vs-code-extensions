import re
from tracemalloc import start
from typing import List

from server.ats.trees.blueprint_v2 import (
    BlueprintV2OutputNode,
    BlueprintV2Tree,
    FreeFormNode,
    FreeFormProperty,
    GrainNode,
    GrainObject,
    GrainSpecNode,
    GrainSpecScripts,
    GrainSpecTargetObject,
    RunnerConfigurationOverrideObject,
    ScriptObject,
    ScriptOutputsObject,
    SpecHostNode,
    WorkflowObject,
    WorkflowTriggerObject,
)
from server.ats.trees.common import NodeError, SequenceNode, TextNode, YamlNode
from server.validation.common import ValidationHandler
from pygls.workspace import Document
from pygls.lsp.types.basic_structures import DiagnosticSeverity


# a '{{ ... }}' expression; compiled once instead of on every visited node
EXPRESSION_REGEX = re.compile(r"\{\{[^\{\}]*\}\}")


class ExpressionValidationVisitor:
    reserved_words = [
        "sandboxid",
        "envid",
        "environmentname",
        "blueprintname",
        "owneremail",
        "accountname",
        "spacename",
    ]
    prefixes = ["inputs", "grains", "params", "resources", "env_references"]
    pipe_commands = ["downcase", "key_access", "strip"]
    grains_props = ["outputs", "scripts"]

    def __init__(self, tree: BlueprintV2Tree) -> None:
        self.tree = tree
        self.processors_map = {
            GrainNode: self._do_process_grain,
            BlueprintV2OutputNode: self._do_process_blueprint_output,
        }
        
    def visit_node(self, node: YamlNode):
        # Free form sections are opaque to the server (a customization launch
        # form uses the UI's own template dialect, an ansible inventory-file may
        # hold Jinja), so their content is not grain Liquid and must not be
        # validated as such. Skipping the node also skips its whole subtree.
        if isinstance(node, (FreeFormNode, FreeFormProperty)):
            return

        if isinstance(node, TextNode) and node.allow_vars:
            node_text = node.text

            exprs = EXPRESSION_REGEX.finditer(node_text)

            for match in exprs:
                expression = match.group()[2:-2].strip()
                offset = match.span()
                if node.style:
                    offset = (offset[0] + 1, offset[1] + 1)

                error = self.validate_expression(expression, node)

                if error:
                    node.add_error(
                        NodeError(
                            start_pos=(node.start_pos[0], node.start_pos[1] + offset[0]),
                            end_pos=(node.end_pos[0], node.start_pos[1] + offset[1]),
                            message=error
                    ))                

        for child in node.get_children():
            self.visit_node(child)

    def validate_expression(self, expression: str, node: YamlNode) -> str:
        if not expression:
            return "Expression could not be empty"

        if "|" in expression:
            parts = [p.strip() for p in expression.split("|")]
            if len(parts) != 2:
                return "Too many pipes in expression. Only one is allowed"

            # a filter may take arguments: 'key_access: "hostname"'
            command = parts[1].split(":")[0].strip()

            if command not in self.pipe_commands:
                return f"Unknown command {command}"
            else:
                expression = parts[0]

        if not expression.startswith("."):
            if expression.lower() not in self.reserved_words:
                return f"The value '{expression}' is not a reserved variable"

        else:
            if expression.endswith("."):
                return "Trailing period symbol is not allowed"

            expr_parts = expression.split(".")[1:]
            if expr_parts[0] not in self.prefixes:
                return f"Prefix '.{expr_parts[0]}' is not allowed"

            node_to_process = self._find_nearest_available_node(node)
            if node_to_process:
                helper_func = self.processors_map.get(type(node_to_process), None)
                if helper_func:
                    return helper_func(expr_parts, node_to_process)

    def _find_nearest_available_node(self, node: YamlNode):
        while (node):
            node_class = type(node)
            if node_class in self.processors_map:
                return node
            node = node.parent
        
    def _do_process_grain(self, parts: List[str], node: GrainNode):
        return self._expression_parts_validate(parts, node, True)

    def _do_process_blueprint_output(self, parts: List[str], node: GrainNode):
        return self._expression_parts_validate(parts, node)

    def _expression_parts_validate(
        self, parts: List[str],
        node: YamlNode,
        is_grain_object: bool = False):

        if len(parts) == 0 or node.value is None:
            return None

        if parts[0] == "grains":
            try:
                dep_grain = parts[1]

                if is_grain_object:
                    refered_deps_names = [d["name"] for d in node.value.get_deps()]
                    # check grain name
                    if dep_grain == node.identifier:
                        return "Grain cannot refer to itself"
                    elif dep_grain not in refered_deps_names:
                        return f"You must list referred grain '{dep_grain}' in depends-on property"

                elif dep_grain not in self.tree.get_grains_names():
                    return f"Grain '{dep_grain}' is not defined"

                # check if 'outputs' is followed after grain name
                if parts[2] not in self.grains_props:
                    return f"Wrong property '{parts[2]}'. Must be in {self.grains_props}."

                grain_prop = parts[2]

                # '.grains.<grain>.outputs' with nothing after it refers to the
                # whole outputs map (usually piped into key_access) and is valid
                if grain_prop == "outputs" and len(parts) == 3:
                    return None

                output: str = ''

                dep_grain_node = self.tree.grains.get_mapping_by_key(dep_grain)

                if dep_grain_node is None:
                    return f"Grain {dep_grain} is not defined"

                spec_node: GrainSpecNode = dep_grain_node.get_value().spec

                if spec_node is None or spec_node.value is None:
                    return f"Grain '{dep_grain}' does not have outputs"

                if grain_prop == "scripts":
                    script_type = parts[3]
                    # a grain without a 'scripts' section has no property to
                    # take the value from (PropertyNode proxies it to None)
                    scripts_prop = getattr(spec_node, "scripts", None)
                    scripts: GrainSpecScripts = getattr(scripts_prop, "value", None)

                    if scripts is None:
                        return f"Scripts are not a defined in the grain '{dep_grain}'"
                    script = getattr(scripts, script_type, None)

                    if not script or not script.value or not isinstance(script.value, ScriptOutputsObject):
                        return f"Wrong type of the script '{script_type}'"

                    else:
                        script = script.value

                    if parts[4] != "outputs":
                        return f"Wrong script property '{parts[5]}."

                    output = parts[5]
                    outputs_names = [output.text for output in script.get_outputs()]
                else:
                    output = parts[3]
                    outputs_names = [spec.text for spec in spec_node.value.get_outputs()]
                error_msg = f"Output '{output}' is not part of the '{dep_grain}' grain's outputs"
                if output not in outputs_names:
                    return error_msg

            except IndexError: 
                return f"Incomplete expression"

        elif parts[0] == "inputs":
            if len(parts) != 2:
                return "Not a valid expression"

            input_name = parts[1]
            inputs_node = self.tree.inputs

            if inputs_node is None or inputs_node.get_mapping_by_key(input_name) is None:
                return f"Input '{input_name}' is not defined in a blueprint"


class BlueprintSpec2Validator(ValidationHandler):
    def __init__(self, tree: BlueprintV2Tree, document: Document) -> None:
        self.tree = tree
        super().__init__(tree, document)

    def _get_grains_names(self):
        return [node.key.text for node in self.tree.grains.nodes]

    def _validate_no_duplicates_in_grain_outputs(self):
        message = "Multiple declarations of output '{}'"

        for _, _, spec in self._grain_specs():
            outputs_list = spec.get_outputs()
            outputs_names = [output.text.lower() for output in outputs_list]

            for output_node in outputs_list: 
                if outputs_names.count(output_node.text.lower()) > 1:
                    self._add_diagnostic(
                        output_node, message=message.format(output_node.text)
                    )
    
    def _validate_no_duplicates_in_grain_spec(self):
        for _, _, spec in self._grain_specs():
            grain_inputs = spec.get_inputs()
            inputs_keys = [i.key.text for i in grain_inputs]

            for input_node in grain_inputs:
                if inputs_keys.count(input_node.key.text) > 1:
                    self._add_diagnostic(
                        node=input_node.key,
                        message=f"Duplicated input name '{input_node.key.text}'")

    def _check_unused_blueprint_inputs(self):
        for input_node in self.tree.input_list:
            input_name = input_node.key.text
            doc_lines = self._document.lines
            match = []
            
            regex = re.compile("^(?!.*#).*\{\{\s*.inputs\.(" + input_name + ")\s*\}\}")

            for line in doc_lines:
                match += regex.findall(line)
    
            if not match:

                self._add_diagnostic(
                    node = input_node.key,
                    message=f"The defined input '{input_name}' is not accessed",
                    diag_severity=DiagnosticSeverity.Warning
                )
            
    def _validate_grain_dep_exists(self):
        for grain in self.tree.grain_nodes:
            grain_name = grain.key.text
            grains_list = self._get_grains_names()
            deps = grain.value.get_deps() if grain.value else None

            if deps is None:
                continue

            for d in deps:
                start_pos = d["start"]
                end_pos = d["end"]

                if d["name"] not in grains_list:
                    self._add_diagnostic(
                        start_pos=(start_pos.line, start_pos.col),
                        end_pos=(end_pos.line, end_pos.col),
                        message=f"The grain '{grain_name}' depends on undefined grain {d['name']}"
                    )
                if d["name"] == grain_name:
                    self._add_diagnostic(
                        start_pos=(start_pos.line, start_pos.col),
                        end_pos=(end_pos.line, end_pos.col),
                        message=f"The grain '{grain_name}' cannot be dependent on itself",
                    )

    def _validate_no_duplicates_in_deps(self):
        for grain in self.tree.grain_nodes:
            grain_obj: GrainObject = grain.value

            # an empty grain must not stop the following grains from being checked
            if grain_obj is None:
                continue

            deps = grain_obj.get_deps()
            deps_names = [d["name"] for d in deps]

            for d in deps:
                start_pos = d["start"]
                end_pos = d["end"]
                grain = d["name"]
                if deps_names.count(d["name"]) > 1:
                    self._add_diagnostic(
                        start_pos=(start_pos.line, start_pos.col),
                        end_pos=(end_pos.line, end_pos.col),
                        message=f"Multiple mentioning of grain '{grain}'",
                    )
            
    # -----------------------------------------------------------------
    # Helpers shared by the semantic validations below.
    # The document is validated while it is being typed, so any node may
    # be missing or only partially initialized. Everything here returns
    # None instead of raising: an exception would discard all diagnostics.
    # -----------------------------------------------------------------
    @staticmethod
    def _prop_value(prop, expected_type: type = None):
        """Returns the value node of a property ('mode: data' -> the scalar
        holding 'data'). None when the property is absent, has no value yet
        or its value is not of the expected type."""
        if prop is None:
            return None

        value = getattr(prop, "value", None)

        if value is None:
            return None

        if expected_type is not None and not isinstance(value, expected_type):
            return None

        return value

    @classmethod
    def _prop_text(cls, prop) -> str:
        """Text of a scalar property value, or None if there is no scalar."""
        value = cls._prop_value(prop, TextNode)

        if value is None or not value.text:
            return None

        return value.text.strip()

    @staticmethod
    def _is_expression(text: str) -> bool:
        """A Liquid expression cannot be validated statically."""
        return text is not None and "{{" in text

    @classmethod
    def _is_explicit_false(cls, prop) -> bool:
        text = cls._prop_text(prop)

        if text is None or cls._is_expression(text):
            return False

        return text.lower() == "false"

    @staticmethod
    def _anchor(*nodes) -> YamlNode:
        """First of the given nodes which can carry a diagnostic."""
        for node in nodes:
            if node is None:
                continue

            if node.start_pos is not None and node.end_pos is not None:
                return node

        return None

    def _report(self, message: str, *nodes):
        anchor = self._anchor(*nodes)

        if anchor is not None:
            self._add_diagnostic(node=anchor, message=message)

    def _grain_specs(self):
        """(grain node, grain object, spec node) of every grain having a spec.
        Grains without one are skipped: 'spec:' with nothing under it yet is a
        property without a value, and PropertyNode proxies attribute access to
        that value, so 'spec.get_outputs' would resolve to None, not a method."""
        result = []

        for grain in self.tree.grain_nodes:
            grain_obj: GrainObject = grain.value

            if grain_obj is None:
                continue

            spec = self._prop_value(grain_obj.spec, GrainSpecNode)

            if spec is None:
                continue

            result.append((grain, grain_obj, spec))

        return result

    # -----------------------------------------------------------------
    # Semantic validations
    # -----------------------------------------------------------------
    def _validate_resource_requirements(self):
        message = (
            "A resource requirement must have exactly one of "
            "'selector' or 'reference'"
        )

        requirements = self._prop_value(self.tree.resources, SequenceNode)

        if requirements is None:
            return

        for requirement in requirements.nodes:
            requirement_obj = requirement.value

            selector = getattr(requirement_obj, "selector", None)
            reference = getattr(requirement_obj, "reference", None)

            # exactly one of them must be there
            if (selector is None) == (reference is None):
                self._report(message, requirement.key, requirement)

    def _validate_agent_and_target_exclusivity(self):
        message = (
            "A grain cannot define both 'agent' and 'target'. "
            "Use 'target' to run on a specific execution target"
        )

        for grain, _, spec in self._grain_specs():
            if spec.agent is not None and spec.target is not None:
                self._report(
                    message,
                    getattr(spec.agent, "key", None),
                    spec.agent,
                    grain.key,
                )

    # The allowed values per kind mirror cs2018's GrainModeValidator options:
    # terraform accepts Managed and NoTermination, argocd accepts Data only and
    # requires it explicitly, every other kind accepts Managed only.
    grain_modes = {
        "terraform": ["managed", "no-termination"],
        "argocd": ["data"],
    }
    default_grain_modes = ["managed"]
    kinds_requiring_mode = ["argocd"]

    def _validate_grain_mode(self):
        for grain, grain_obj, spec in self._grain_specs():
            kind = self._prop_text(grain_obj.kind)

            if kind is None or self._is_expression(kind):
                continue

            kind_key = kind.lower()
            allowed = self.grain_modes.get(kind_key, self.default_grain_modes)
            mode = self._prop_text(spec.mode)

            if mode is None:
                if kind_key in self.kinds_requiring_mode:
                    self._report(
                        "A grain of kind '{}' must define mode '{}'".format(
                            kind, allowed[0]
                        ),
                        getattr(grain_obj.spec, "key", None),
                        grain.key,
                        grain,
                    )
                continue

            if self._is_expression(mode):
                continue

            if mode not in allowed:
                self._report(
                    "Invalid mode '{}' for a grain of kind '{}'. "
                    "Allowed values are: {}".format(mode, kind, ", ".join(allowed)),
                    self._prop_value(spec.mode, TextNode),
                    spec.mode,
                    grain.key,
                )

    def _get_use_storage_property(self, spec: GrainSpecNode):
        """'use-storage' of the grain's execution host, either declared
        directly on the agent or in the target's runner override."""
        agent = self._prop_value(spec.agent, SpecHostNode)

        if agent is not None and agent.use_storage is not None:
            return agent.use_storage

        target = self._prop_value(spec.target, GrainSpecTargetObject)

        if target is None:
            return None

        override = self._prop_value(
            target.runner_configuration_override, RunnerConfigurationOverrideObject
        )

        if override is None:
            return None

        return override.use_storage

    def _validate_auto_approve_requires_storage(self):
        message = (
            "A grain with 'auto-approve: false' cannot run with "
            "'use-storage: false': the runner needs storage to keep the plan "
            "until it is approved"
        )

        for grain, _, spec in self._grain_specs():
            if not self._is_explicit_false(spec.auto_approve):
                continue

            use_storage = self._get_use_storage_property(spec)

            if self._is_explicit_false(use_storage):
                self._report(
                    message,
                    self._prop_value(use_storage, TextNode),
                    use_storage,
                    grain.key,
                )

    workflow_scopes = ["space", "env", "env_resource"]
    workflow_min_timeout = 5

    def _validate_workflow(self):
        workflow = self._prop_value(self.tree.workflow, WorkflowObject)

        if workflow is None:
            return

        scope = self._validate_workflow_scope(workflow)
        self._validate_workflow_triggers(workflow, scope)
        self._validate_workflow_timeout(workflow)

    def _validate_workflow_scope(self, workflow: WorkflowObject) -> str:
        """Validates the scope and returns it in a normalized form."""
        scope = self._prop_text(workflow.scope)

        if scope is None or self._is_expression(scope):
            return None

        if scope.lower() not in self.workflow_scopes:
            self._report(
                "Invalid workflow scope '{}'. Allowed values are: {}".format(
                    scope, ", ".join(self.workflow_scopes)
                ),
                self._prop_value(workflow.scope, TextNode),
                workflow.scope,
                self.tree.workflow,
            )
            return None

        return scope.lower()

    def _validate_workflow_triggers(self, workflow: WorkflowObject, scope: str):
        triggers = self._prop_value(workflow.triggers, SequenceNode)

        if triggers is None:
            return

        for trigger in triggers.nodes:
            if not isinstance(trigger, WorkflowTriggerObject):
                continue

            trigger_type = self._prop_text(trigger.type)

            if trigger_type is None or self._is_expression(trigger_type):
                continue

            trigger_type = trigger_type.lower()
            fallbacks = (
                self._prop_value(trigger.type, TextNode),
                trigger.type,
                trigger,
            )

            has_event = self._has_events(trigger)
            has_cron = self._prop_text(trigger.cron) is not None

            if scope == "space" and trigger_type in ["cron", "event"]:
                self._report(
                    "A space scoped workflow supports manual triggers only, "
                    "not a trigger of type '{}'".format(trigger_type),
                    *fallbacks
                )

            if trigger_type == "manual":
                if has_event or has_cron:
                    self._report(
                        "A trigger of type 'manual' cannot define "
                        "'event' or 'cron'",
                        *fallbacks
                    )

            elif trigger_type == "event":
                if not has_event:
                    self._report(
                        "A trigger of type 'event' must define at least "
                        "one 'event'",
                        *fallbacks
                    )
                if has_cron:
                    self._report(
                        "A trigger of type 'event' cannot define 'cron'",
                        *fallbacks
                    )

            elif trigger_type == "cron":
                if not has_cron:
                    self._report(
                        "A trigger of type 'cron' must define 'cron'", *fallbacks
                    )
                if has_event:
                    self._report(
                        "A trigger of type 'cron' cannot define 'event'", *fallbacks
                    )

    def _has_events(self, trigger: WorkflowTriggerObject) -> bool:
        # 'event' has to be a list: a scalar never reaches validation, the
        # parser rejects it just like the server rejects the scalar form
        events = self._prop_value(trigger.event, SequenceNode)

        return events is not None and len(events.nodes) > 0

    def _validate_workflow_timeout(self, workflow: WorkflowObject):
        timeout = self._prop_text(workflow.timeout)

        if timeout is None or self._is_expression(timeout):
            return

        message = "Workflow 'timeout' must be an integer of at least {}".format(
            self.workflow_min_timeout
        )

        try:
            valid = int(timeout) >= self.workflow_min_timeout
        except ValueError:
            valid = False

        if not valid:
            self._report(
                message,
                self._prop_value(workflow.timeout, TextNode),
                workflow.timeout,
                self.tree.workflow,
            )

    def validate(self):
        visitor = ExpressionValidationVisitor(self.tree)
        self.tree.accept(visitor)

        # warnings
        self._check_unused_blueprint_inputs()

        # errors
        self._validate_grain_dep_exists()
        self._validate_no_duplicates_in_grain_outputs()
        self._validate_no_duplicates_in_deps()
        self._validate_no_duplicates_in_grain_spec()
        self._validate_resource_requirements()
        self._validate_agent_and_target_exclusivity()
        self._validate_grain_mode()
        self._validate_auto_approve_requires_storage()
        self._validate_workflow()
        return self._diagnostics
