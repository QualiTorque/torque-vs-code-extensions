
from server.ats.trees.common import *


@dataclass
class ServiceResourceNode(ResourceNode):
    pass


@dataclass
class ApplicationResourceNode(ResourceNode):
    # TODO: add handling to parser
    target: TextNode = None
    instances: TextNode = None


@dataclass
class ApplicationNode(MappingNode):
    key: TextNode = None
    value: ApplicationResourceNode = None


@dataclass
class ServiceNode(MappingNode):
    key: TextNode = None
    value: ServiceResourceNode = None


@dataclass
class AppsSequence(SequenceNode):
    node_type = ApplicationNode


@dataclass
class ServicesSequence(SequenceNode):
    node_type = ServiceNode


@dataclass
class BlueprintTree(BaseTree):
    applications: AppsSequence = None
    services: ServicesSequence = None

    # applications: Optional[ResourcesContainerNode] = field(init=False)
    # services: Optional[ResourcesContainerNode] = field(init=False)
    # artifacts: List[MappingNode] = field(default_factory=list)
    #
    # def __post_init__(self):
    #     self.services = ResourcesContainerNode(parent=self)
    #     self.applications = ResourcesContainerNode(parent=self)
