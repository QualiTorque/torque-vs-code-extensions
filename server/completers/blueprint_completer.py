from server.ats.trees.common import BaseTree, ScalarNode, TreeWithOutputs
from typing import List
from server.utils import applications, services
from server.utils.common import get_line_before_position, get_path_to_pos
from server.ats.trees.blueprint import BlueprintResourceMappingNode, BlueprintTree
from pygls.lsp.types.language_features.completion import CompletionItem, CompletionItemKind, CompletionParams
from pygls.workspace import Workspace
from server.completers.base import Completer


class BlueprintResourceCompleter(Completer):
    def __init__(self, workspace: Workspace, params: CompletionParams, tree: BlueprintTree) -> None:
        super().__init__(workspace, params, tree)
        self.path = get_path_to_pos(self.tree, self.params.position)

    def get_completions(self) -> List[CompletionItem]:
        if len(self.path) < 3:
            return []

        try:
            resources = self._get_resources()
        except ValueError:
            return []

        doc = self.workspace.get_document(self.params.text_document.uri)
        pos = self.params.position
        line_before_pos = get_line_before_position(doc, pos)

        items = []
        for res, res_details in resources.items():
            tree = res_details.get("tree", None)

            if not tree:
                continue

            props = self._build_resource_completion(res, tree)
            label = res

            if self.path[-1] == self._get_resource_sequence() and line_before_pos.endswith("-"):
                props = "- " + props
                label = "- " + res

            elif not (isinstance(self.path[-1], ScalarNode)
                      and isinstance(self.path[-2], BlueprintResourceMappingNode)):
                seq = self._get_resource_sequence()
                col = seq.nodes[0].start_pos[1] if seq.nodes else 4  # get default
                char = self.params.position.character

                if char != col - 2 or char == 0:
                    return []

                else:
                    props = "- " + props

            items.append(CompletionItem(
                label=label,
                kind=CompletionItemKind.Reference,
                insert_text=props
            ))
        return items

    def _get_resource_sequence(self):
        for item in self.path:
            if isinstance(item, (BlueprintTree.AppsSequence, BlueprintTree.ServicesSequence)):
                return item
        raise ValueError

    def _get_resources(self) -> dict:
        try:
            seq = self._get_resource_sequence()
        except ValueError:
            raise
        root = self.workspace.root_path  # TODO: workspace's root could not be a root of blueprint repo. Handle
        return (applications.get_available_applications(root)
                if isinstance(seq, BlueprintTree.AppsSequence)
                else services.get_available_services(root))

    def _build_resource_completion(self, resource_name: str, tree: BaseTree) -> str:
        tab = "  "
        output = f"{resource_name}:\n"
        if tree.kind.text == "application":
            output += tab * 2 + "instances: 1\n"

        inputs = tree.get_inputs()
        if inputs:
            output += tab * 2 + "input_values:\n"
            for input in inputs:
                if input.value:
                    output += tab * 3 + f"- {input.key.text}: {input.value.text}\n"
                else:
                    output += tab * 3 + f"- {input.key.text}: \n"

        return output
