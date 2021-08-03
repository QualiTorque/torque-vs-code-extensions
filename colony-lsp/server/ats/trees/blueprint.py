from typing import Union

from server.ats.trees.common import *


@dataclass
class InfrastructureNode(YamlNode):

    @dataclass
    class ConnectivityNode(YamlNode):

        @dataclass
        class VirtualNetwork(YamlNode):

            @dataclass
            class SubnetsNode(YamlNode):
                gateway: TextNodesSequence = None
                management: TextNodesSequence = None
                application: TextNodesSequence = None

            id: TextNode = None
            subnets: SubnetsNode = None

        green_host: TextNode = None
        virtual_network: VirtualNetwork = None

    stack: TextNode = None
    connectivity: ConnectivityNode = None


@dataclass
class MetadataNode(YamlNode):
    description: TextNode = None
    tags: TextNodesSequence = None


@dataclass
class RuleNode(YamlNode):
    path: TextNode = None
    host: TextNode = None
    application: TextNode = None
    port: TextNode = None
    color: TextNode = None
    shortcut: TextNode = None
    default: TextNode = None


@dataclass
class RulesSequenceNode(SequenceNode):
    node_type = RuleNode


@dataclass
class ListenerNode(YamlNode):
    http: TextNode = None
    redirect_to_listener: TextNode = None
    https: TextNode = None
    certificate: TextNode = None
    rules: RulesSequenceNode = None


@dataclass
class ListenersSequenceNode(SequenceNode):
    node_type = ListenerNode


@dataclass
class IngressNode(YamlNode):
    enabled: TextNode = None
    listeners: ListenersSequenceNode = None


@dataclass
class DebuggingNode(YamlNode):
    bastion_availability: TextNode = None
    direct_access: TextNode = None
    availability: TextNode = None


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
    depends_on: TextNodesSequence = None


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
    artifacts: TextMappingSequence = None
    clouds: TextMappingSequence = None
    metadata: MetadataNode = None
    debugging: DebuggingNode = None
    ingress: IngressNode = None
    infrastructure: InfrastructureNode = None
