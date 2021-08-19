from abc import ABC
from dataclasses import dataclass
from server.ats.trees.common import (BaseTree, ResourceMappingNode, SequenceNode,
                                     TextNode, TreeWithOutputs, ScalarNode, ObjectNode)


@dataclass
class DebuggingNode(ObjectNode):
    allow_direct_access: ScalarNode = None
    connection_protocol: ScalarNode = None


@dataclass
class SpecNode(ObjectNode):
    @dataclass
    class KubernetesSpecNode(ObjectNode):
        cpu: TextNode = None
        ram: TextNode = None

    @dataclass
    class AwsSpecNode(ObjectNode):
        instance_type: TextNode = None

    @dataclass
    class AzureSpecNode(ObjectNode):
        vm_size: TextNode = None

    azure: AzureSpecNode = None
    aws: AwsSpecNode = None
    kubernetes: KubernetesSpecNode = None


@dataclass
class IngressHealthCheckNode(ObjectNode):
    healthy_threshold: ScalarNode = None
    interval: ScalarNode = None
    path: ScalarNode = None
    status_code: ScalarNode = None
    timeout: ScalarNode = None
    unhealthy_threshold: ScalarNode = None

    def _get_field_mapping(self) -> {str: str}:
        mapping = super()._get_field_mapping()
        mapping.update({
            "healthy-threshold": "healthy_threshold",
            "status-code": "status_code",
            "unhealthy-threshold": "unhealthy_threshold"
        })
        return mapping


@dataclass
class PortInfoNode(ObjectNode):
    port: TextNode = None
    path: TextNode = None


@dataclass
class PortInfoInternalNode(PortInfoNode):
    ingress_healthcheck: IngressHealthCheckNode = None
    port_range: TextNode = None

    def _get_field_mapping(self) -> {str: str}:
        mapping = super()._get_field_mapping()
        mapping.update({
            "port-range": "port_range",
            "ingress-healthcheck": "ingress_healthcheck"
        })
        return mapping


@dataclass
class ExternalPortInfoMappingNode(ResourceMappingNode):
    value: PortInfoNode = None


@dataclass
class InternalPortInfoMappingNode(ResourceMappingNode):
    value: PortInfoInternalNode = None


@dataclass
class InfrastructureNode(ObjectNode):
    @dataclass
    class ComputeNode(ObjectNode):
        spec: SpecNode = None

    @dataclass
    class ConnectivityNode(ObjectNode):
        @dataclass
        class ExternalPortsSequenceNode(SequenceNode):
            node_type = ExternalPortInfoMappingNode

        @dataclass
        class InternalPortsSequenceNode(SequenceNode):
            node_type = InternalPortInfoMappingNode

        external: ExternalPortsSequenceNode = None
        internal: InternalPortsSequenceNode = None

    @dataclass
    class InfraPermissionsNode(ObjectNode):
        @dataclass
        class InfraAwsPermissionsNode(ObjectNode):
            iam_instance_profile: TextNode = None

        @dataclass
        class InfraAzurePermissionsNode(ObjectNode):
            managed_identity_id: TextNode = None

        aws: InfraAwsPermissionsNode = None
        azure: InfraAzurePermissionsNode = None

    compute: ComputeNode = None
    connectivity: ConnectivityNode = None
    permissions: InfraPermissionsNode = None


@dataclass
class ConfigurationNode(ObjectNode):
    @dataclass
    class InitializationNode(ObjectNode):
        script: ScalarNode = None

    @dataclass
    class StartNode(InitializationNode):
        command: ScalarNode = None

    @dataclass
    class HealthcheckNode(InitializationNode):
        timeout: ScalarNode = None
        wait_for_ports: TextNode = None

    initialization: InitializationNode = None
    start: StartNode = None
    healthcheck: HealthcheckNode = None


@dataclass
class AmiImageNode(ObjectNode):
    id: TextNode = None
    region: ScalarNode = None
    username: ScalarNode = None


@dataclass
class AzureImageProps(ABC):
    subscription_id: TextNode = None
    resource_group: TextNode = None
    image: TextNode = None


@dataclass
class AzureImageNode(ObjectNode):
    @dataclass
    class AzureGalleryImageNode(AzureImageProps, ObjectNode):
        shared_image_gallery: TextNode = None
        image_definition: TextNode = None
        image_version: TextNode = None

    @dataclass
    class AzureCustomImageNode(AzureImageProps, ObjectNode):
        image: TextNode = None

    urn: TextNode = None
    username: TextNode = None
    custom_image: AzureCustomImageNode = None
    gallery: AzureGalleryImageNode = None
    custom: TextNode = None


@dataclass
class DockerImageNode(ObjectNode):
    name: ScalarNode = None
    pull_secret: TextNode = None
    tag: ScalarNode = None
    username: TextNode = None


@dataclass
class AmiSequenceNode(SequenceNode):
    node_type = AmiImageNode


@dataclass
class AzureSequenceNode(SequenceNode):
    node_type = AzureImageNode


@dataclass
class DockerImagesSequence(SequenceNode):
    node_type = DockerImageNode


@dataclass
class SourceNode(ObjectNode):
    @dataclass
    class ImageNode(ObjectNode):
        ami: AmiSequenceNode = None
        azure_image: AzureSequenceNode = None
        docker_image: DockerImagesSequence = None

    image: ImageNode = None
    os_type: ScalarNode = None


@dataclass
class AppTree(TreeWithOutputs, BaseTree):
    configuration: ConfigurationNode = None
    source: SourceNode = None
    debugging: DebuggingNode = None
    infrastructure: InfrastructureNode = None
    # old syntax
    ostype: TextNode = None
