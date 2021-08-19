from dataclasses import dataclass
from server.ats.trees.common import (BaseTree, PropertyNode, ScalarMappingsSequence, MappingNode, SequenceNode,
                                     TextMappingSequence, TextNode, ScalarNodesSequence, ScalarNode,
                                     TextNodesSequence, ObjectNode)
from typing import List, Union


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
        deps: PropertyNode = self.depends_on

        if deps is None or deps.value is None:
            return []

        seq: ScalarNodesSequence = deps.value
        return seq.nodes 
        

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
    def depends_on(self):
        return self.value.get_dependencies()


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
        tags: ScalarNodesSequence = None

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

    def get_applications(self) -> List[ApplicationResourceNode]:
        apps: PropertyNode = self.applications

        if apps is None or apps.value is None:
            return []

        return [node for node in apps.value.nodes]

    def get_services(self) -> List[ServiceResourceNode]:
        srvs: PropertyNode = self.services

        if srvs is None or srvs.value is None:
            return []

        return [node for node in srvs.value.nodes]
