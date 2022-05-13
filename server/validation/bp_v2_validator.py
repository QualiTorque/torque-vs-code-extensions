import re
from typing import List

from server.ats.trees.blueprint_v2 import BlueprintV2OutputNode, BlueprintV2Tree, GrainNode
from server.ats.trees.common import NodeError, TextNode, YamlNode
from server.validation.common import ValidationHandler
from pygls.workspace import Document


class ExpressionValidationVisitor:
    reserved_words = ["sandboxid"]
    prefixes = ["inputs", "grains"]
    pipe_commands = ["downcase"]

    def __init__(self, tree: BlueprintV2Tree) -> None:
        self.tree = tree
        self.processors_map = {
            GrainNode: self._do_process_grain,
            BlueprintV2OutputNode: self._do_process_blueprint_output,
        }
        
    def visit_node(self, node: YamlNode):
        if isinstance(node, TextNode) and node.allow_vars:
            node_text = node.text

            regex = re.compile("\{\{[^\{\}]*\}\}")
            exprs = regex.finditer(node_text)

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
            elif parts[1] not in self.pipe_commands:
                return f"Unknown command {parts[1]}"
            else:
                expression = parts[0]

        if not expression.startswith("."):
            if expression not in self.reserved_words:
                return f"The value '{expression}' is not a reserved variable"

        else:
            if expression.endswith("."):
                return "trailing period symbol is not allowed"

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
                    # check grain name
                    if dep_grain == node.identifier:
                        return "Grain cannot refer to itself"
                    elif dep_grain not in node.value.get_deps():
                        return f"You must list referred grain '{dep_grain}' in depends-on property"

                elif dep_grain not in self.tree.get_grains_names():
                    return f"Grain '{dep_grain}' is not defined"

                # check if 'outputs' is followed after grain name
                if parts[2] != "outputs":
                    return f"You can access only 'outputs' property of grain '{dep_grain}'"

                output = parts[3]
                error_msg = f"Output '{output}' is not defined in spec of grain '{dep_grain}'"
                dep_grain_node = self.tree.grains.get_mapping_by_key(dep_grain)                
                spec_node = dep_grain_node.get_value().spec

                if spec_node is None or spec_node.value is None:
                    return error_msg

                outputs_names = [spec.text for spec in spec_node.value.get_outputs()]
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
    
    def _validate_grain_dep_exists(self):
        for grain in self.tree.grains.nodes:
            grain_name = grain.key.text
            grains_list = self._get_grains_names()
            # depend = grain.value.depends_on if grain.value else None
            deps = grain.value.get_deps() if grain.value else None

            if deps is None:
                continue

            for d, pos in deps.items():
                if d not in grains_list:
                    self._add_diagnostic(
                        start_pos=(pos[0].line, pos[0].col),
                        end_pos=(pos[1].line, pos[1].col),
                        message=f"The grain '{grain_name}' depends on undefined grain {d}"
                    )
                if d == grain_name:
                    self._add_diagnostic(
                        start_pos=(pos[0].line, pos[0].col),
                        end_pos=(pos[1].line, pos[1].col),
                        message=f"The grain '{grain_name}' cannot be dependent on itself",
                    )
            
    def validate(self):
        visitor = ExpressionValidationVisitor(self.tree)
        self.tree.accept(visitor)

        self._validate_grain_dep_exists()
        return self._diagnostics
