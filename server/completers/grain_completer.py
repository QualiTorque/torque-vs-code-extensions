from re import X
from typing import List

from pygls.lsp.types.language_features.completion import (
    CompletionItem,
    CompletionItemKind
)
from pygls.workspace import Workspace
from pyparsing import PrecededBy

from server.ats.trees.blueprint_v2 import BlueprintV2Tree, GrainNode
from server.ats.trees.common import PropertyNode, YamlNode

from server.completers.base import Completer


class GrainObjectCompleter(Completer):
    def get_completions(self) -> List[CompletionItem]:
        proccessing_funcs = {
            "depends_on": self._process_depends_on
        }
        property = self._find_nearest_prop()
        func = proccessing_funcs.get(property.identifier, None)

        if func is None:
            return []

        return func(property)

    def _process_depends_on(self, property_node: PropertyNode):
        completions_items = []

        cur_grain_name = self._get_grain_name()
        grains_names_list = self.tree.get_grains_names()
        typed = "" if property_node.value is None else property_node.value.text

        for name in grains_names_list:
            if name in [cur_grain_name, typed]:
                continue
            if name.startswith(typed):
                completions_items.append(CompletionItem(label=name, kind=CompletionItemKind.Reference))

        return completions_items

    def _get_grain_name(self) -> str:
        for item in reversed(self.path):
            if isinstance(item, GrainNode):
                return item.identifier

    def _find_nearest_prop(self):
        for node in reversed(self.path):
            if isinstance(node, PropertyNode):
                return node
            if isinstance(node, GrainNode):
                return None
        
        return None


       