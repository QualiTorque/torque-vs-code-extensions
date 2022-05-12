import re

from server.ats.trees.blueprint_v2 import BlueprintV2Tree
from server.ats.trees.common import NodeError, ScalarNode, TextNode, YamlNode
from server.validation.common import ValidationHandler
from pygls.workspace import Document


class ExpressionValidationVisitor:
    reserved_words = ["sandboxId"]
    prefixes = ["inputs", "grains"]
        
    def visit_node(self, node: YamlNode):
        if isinstance(node, TextNode) and node.allow_vars:
            node_text = node.text

            regex = re.compile("\{\{[^\{\}]*\}\}")
            exprs = regex.finditer(node_text)

            for match in exprs:
                expression = match.group()[2:-2].strip()
                offset = match.span()
                error = self.validate_basic(expression)

                if error:
                    node.add_error(
                        NodeError(
                            start_pos=(node.start_pos[0], node.start_pos[1] + offset[0]),
                            end_pos=(node.end_pos[0], node.start_pos[1] + offset[1]),
                            message=error
                    ))

        for child in node.get_children():
            self.visit_node(child)

    def validate_basic(self, expression: str) -> str:
        if not expression:
            return "Expression could not be empty"

        if not expression.startswith("."):
            if expression not in self.reserved_words:
                return f"The value '{expression} is not a reserved variable'"

        else:
            if expression.endswith("."):
                return "trailing period symbol is not allowed"

            expr_parts = expression.split(".")[1:]
            if expr_parts[0] not in self.prefixes:
                return f"Prefix .{expr_parts[0]} is not allowed"
            

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
                        dstart_pos=(pos[0].line, pos[0].col),
                        end_pos=(pos[1].line, pos[1].col),
                        message=f"The grain '{grain_name}' cannot be dependent onx§x itself",
                    )
            
    def validate(self):
        visitor = ExpressionValidationVisitor()
        self.tree.accept(visitor)
        self._validate_grain_dep_exists()
        return self._diagnostics
