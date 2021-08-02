
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
class ResourceMappingNode(MappingNode):
    key: TextNode = None

    @property
    def id(self):
        return self.key


@dataclass
class ApplicationNode(ResourceMappingNode):
    value: ApplicationResourceNode = None


@dataclass
class ServiceNode(ResourceMappingNode):
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
