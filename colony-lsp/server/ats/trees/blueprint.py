from dataclasses import dataclass
from server.ats.trees.common import (BaseTree, InputsNode, MappingNode, SequenceNode,
                                     TextMappingSequence, TextNode, ScalarNodesSequence, YamlNode, ScalarNode,
                                     TextNodesSequence)
from typing import Union


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
class RuleNode(YamlNode):
    path: ScalarNode = None
    host: ScalarNode = None
    application: ScalarNode = None
    port: TextNode = None  # yes, numeric
    color: ScalarNode = None  # not green|blue
    shortcut: TextNode = None
    default: ScalarNode = None  # not, true|false
    ignore_exposure: ScalarNode = None
    # new/unsupported
    stickiness: TextNode = None


@dataclass
class ListenerNode(YamlNode):
    @dataclass
    class RulesSequenceNode(SequenceNode):
        node_type = RuleNode

    http: TextNode = None  # yes, numeric
    redirect_to_listener: ScalarNode = None
    https: TextNode = None  # yes, numeric
    certificate: TextNode = None
    rules: RulesSequenceNode = None


@dataclass
class IngressNode(YamlNode):
    @dataclass
    class ListenersSequenceNode(SequenceNode):
        node_type = ListenerNode

    enabled: ScalarNode = None  # true|false
    listeners: ListenersSequenceNode = None


@dataclass
class BlueprintFullInputNode(YamlNode):
    display_style: ScalarNode = None
    description: ScalarNode = None
    default_value: ScalarNode = None
    optional: ScalarNode = None


@dataclass
class BlueprintInputNode(MappingNode):
    key: ScalarNode = None
    value: Union[BlueprintFullInputNode, ScalarNode] = None

    @property
    def default_value(self):
        if isinstance(self.value, BlueprintFullInputNode):
            return self.value.default_value

        if isinstance(self.value, ScalarNode):
            return self.value


@dataclass
class BlueprintInputsSequence(SequenceNode):
    node_type = BlueprintInputNode


@dataclass
class ServiceResourceNode(YamlNode):
    input_values: TextMappingSequence = None
    depends_on: ScalarNodesSequence = None


@dataclass
class ApplicationResourceNode(ServiceResourceNode):
    target: ScalarNode = None
    instances: TextNode = None  # yes, numeric


@dataclass
class BlueprintResourceMappingNode(MappingNode):
    key: ScalarNode = None
    value: ServiceResourceNode = None

    @property
    def id(self):
        return self.key

    @property
    def details(self):
        return self.value


@dataclass
class ApplicationNode(BlueprintResourceMappingNode):
    value: ApplicationResourceNode = None


@dataclass
class ServiceNode(BlueprintResourceMappingNode):
    value: ServiceResourceNode = None


@dataclass
class BlueprintTree(BaseTree):
    @dataclass
    class MetadataNode(YamlNode):
        description: ScalarNode = None
        tags: ScalarNodesSequence = None

    @dataclass
    class AppsSequence(SequenceNode):
        node_type = ApplicationNode

    @dataclass
    class ServicesSequence(SequenceNode):
        node_type = ServiceNode

    @dataclass
    class DebuggingNode(YamlNode):
        bastion_availability: ScalarNode = None
        direct_access: ScalarNode = None
        # old syntax
        availability: ScalarNode = None

    inputs_node: BlueprintInputsSequence = None
    applications: AppsSequence = None
    services: ServicesSequence = None
    artifacts: TextMappingSequence = None
    clouds: TextMappingSequence = None
    metadata: MetadataNode = None
    debugging: DebuggingNode = None
    ingress: IngressNode = None
    infrastructure: InfrastructureNode = None
    # old syntax
    environmentType: TextNode = None
