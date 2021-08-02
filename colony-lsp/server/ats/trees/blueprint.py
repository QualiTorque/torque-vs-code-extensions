from typing import Union

from server.ats.trees.common import *


@dataclass
class BlueprintFullInputNode(YamlNode):
    display_style: TextNode = None
    description: TextNode = None
    default_value: TextNode = None
    optional: TextNode = None


@dataclass
class BlueprintInputNode(MappingNode):
    key: TextNode = None
    value: Union[BlueprintFullInputNode, TextNode] = None

    @property
    def default_value(self):
        if isinstance(self.value, BlueprintFullInputNode):
            return self.value.default_value

        if isinstance(self.value, TextNode):
            return self.value


@dataclass
class BlueprintInputsSequence(SequenceNode):
    node_type = BlueprintInputNode


@dataclass
class ResourceNode(YamlNode):
    input_values: BlueprintInputsSequence = None
    depend_on: TextNodesSequence = None


@dataclass
class ServiceResourceNode(ResourceNode):
    pass


@dataclass
class ApplicationResourceNode(ResourceNode):
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
