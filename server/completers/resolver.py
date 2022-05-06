from typing import List

from server.ats.trees.blueprint import BlueprintTree
from server.ats.trees.blueprint_v2 import GrainObject
from server.ats.trees.common import YamlNode
from server.completers.blueprint_completer import BlueprintResourceCompleter
from server.completers.grain_completer import GrainObjectCompleter


class CompletionResolver:
    completer_map = {
        BlueprintTree.AppsSequence: BlueprintResourceCompleter,
        BlueprintTree.ServicesSequence: BlueprintResourceCompleter,
        GrainObject: GrainObjectCompleter,
    }

    @classmethod
    def get_completer(cls, path: List[YamlNode]):
        for node in reversed(path):
            c = CompletionResolver.completer_map.get(type(node), None)
            if c:
                return c
        raise ValueError
