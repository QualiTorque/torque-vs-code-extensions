from typing import List

from pygls.lsp.types.language_features.completion import (
    CompletionItem,
    CompletionParams,
)
from pygls.workspace import Workspace
from server.ats.trees.common import BaseTree, YamlNode


class Completer:
    def __init__(
        self, workspace: Workspace, params: CompletionParams, tree: BaseTree, path: List[YamlNode]
    ) -> None:
        self.workspace = workspace
        self.params = params
        self.tree = tree
        self.path = path

    def get_completions(self) -> List[CompletionItem]:
        return []
