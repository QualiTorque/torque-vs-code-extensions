from typing import List

from pygls.lsp.types.language_features.completion import (
    CompletionItem,
    CompletionParams,
)
from pygls.workspace import Workspace
from server.ats.trees.common import BaseTree


class Completer:
    def __init__(
        self, workspace: Workspace, params: CompletionParams, tree: BaseTree
    ) -> None:
        self.workspace = workspace
        self.params = params
        self.tree = tree

    def get_completions(self) -> List[CompletionItem]:
        pass
