from dataclasses import dataclass
from typing import List, Union

from server.ats.trees.common import (
    BaseTree,
    MappingNode,
    ObjectNode,
    ScalarMappingsSequence,
    ScalarNode,
    ScalarNodesSequence,
    SequenceNode,
    TextMapping,
    TextMappingSequence,
    TextNode,
    TextNodesSequence,
)


@dataclass
class InfrastructureNode(ObjectNode):
    @dataclass
    class ConnectivityNode(ObjectNode):
        @dataclass
        class VirtualNetwork(ObjectNode):
            @dataclass
            class SubnetsNode(ObjectNode):
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
class RuleNode(ObjectNode):
    path: TextNode = None
    host: TextNode = None
    application: ScalarNode = None
    port: TextNode = None  # yes, numeric
    color: ScalarNode = None  # not green|blue
    shortcut: TextNode = None
    default: ScalarNode = None  # not, true|false
    ignore_exposure: ScalarNode = None
    # new/unsupported
    stickiness: TextNode = None


@dataclass
class ListenerNode(ObjectNode):
    @dataclass
    class RulesSequenceNode(SequenceNode):
        node_type = RuleNode

    http: TextNode = None  # yes, numeric
    redirect_to_listener: ScalarNode = None
    https: TextNode = None  # yes, numeric
    certificate: TextNode = None
    rules: RulesSequenceNode = None


@dataclass
class IngressNode(ObjectNode):
    @dataclass
    class ListenersSequenceNode(SequenceNode):
        node_type = ListenerNode

    enabled: ScalarNode = None  # true|false
    listeners: ListenersSequenceNode = None


@dataclass
class BlueprintFullInputNode(ObjectNode):
    display_style: ScalarNode = None
    description: ScalarNode = None
    default_value: ScalarNode = None
    optional: ScalarNode = None
    possible_values: ScalarNodesSequence = None


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
class ServiceResourceNode(ObjectNode):
    input_values: TextMappingSequence = None
    depends_on: ScalarNodesSequence = None

    def get_dependencies(self) -> List[ScalarNode]:
        return self._get_seq_nodes("depends_on")

    def get_inputs(self) -> List[TextMapping]:
        return self._get_seq_nodes("input_values")


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

    @property
    def deps(self) -> List[ScalarNode]:
        if self.value is None:
            return []
        return self.value.get_dependencies()

    @property
    def inputs(self) -> List[TextMapping]:
        if self.value is None:
            return []
        return self.value.get_inputs()


@dataclass
class ApplicationNode(BlueprintResourceMappingNode):
    value: ApplicationResourceNode = None


@dataclass
class ServiceNode(BlueprintResourceMappingNode):
    value: ServiceResourceNode = None


@dataclass
class BlueprintTree(BaseTree):
    @dataclass
    class MetadataNode(ObjectNode):
        description: ScalarNode = None
        tags: ScalarMappingsSequence = None

    @dataclass
    class AppsSequence(SequenceNode):
        node_type = ApplicationNode

    @dataclass
    class ServicesSequence(SequenceNode):
        node_type = ServiceNode

    @dataclass
    class DebuggingNode(ObjectNode):
        bastion_availability: ScalarNode = None
        direct_access: ScalarNode = None
        # old syntax
        availability: ScalarNode = None

    inputs_node: BlueprintInputsSequence = None
    applications: AppsSequence = None
    services: ServicesSequence = None
    artifacts: TextMappingSequence = None
    clouds: ScalarMappingsSequence = None
    metadata: MetadataNode = None
    debugging: DebuggingNode = None
    ingress: IngressNode = None
    infrastructure: InfrastructureNode = None
    # old syntax
    environmentType: TextNode = None

    def get_inputs(self) -> List[BlueprintInputsSequence]:
        return self._get_seq_nodes("inputs_node")

    def get_artifacts(self) -> List[TextMappingSequence]:
        return self._get_seq_nodes("artifacts")

    def get_applications(self) -> List[ApplicationResourceNode]:
        return self._get_seq_nodes("applications")

    def get_services(self) -> List[ServiceResourceNode]:
        return self._get_seq_nodes("services")
