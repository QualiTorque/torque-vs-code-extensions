from dataclasses import dataclass
from server.ats.trees.common import BaseTree, TreeWithOutputs


@dataclass
class ServiceTree(BaseTree, TreeWithOutputs):
    pass
