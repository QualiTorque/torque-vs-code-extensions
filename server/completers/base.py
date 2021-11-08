from typing import List
from ..ats.trees.common import BaseTree
from pygls.lsp.types.language_features.completion import CompletionItem, CompletionParams
from pygls.workspace import Workspace

class Completer:
    def __init__(self, workspace: Workspace, params: CompletionParams, tree: BaseTree) -> None:
        self.workspace = workspace
        self.params = params
        self.tree = tree

    def get_completions() -> List[CompletionItem]:
        pass
