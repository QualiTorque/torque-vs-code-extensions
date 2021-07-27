
from server.ats.trees.common import *


@dataclass
class ServiceNode(ResourceNode):
    pass


@dataclass
class ApplicationNode(ResourceNode):
    # TODO: add handling to parser
    target = None
    instances = None


@dataclass
class BlueprintTree(BaseTree):
    apps_node: Optional[ResourcesContainerNode] = field(init=False)
    services_node: Optional[ResourcesContainerNode] = field(init=False)
    artifacts: List[MappingNode] = field(default_factory=list)

    def __post_init__(self):
        self.services_node = ResourcesContainerNode(parent=self)
        self.apps_node = ResourcesContainerNode(parent=self) 
