from abc import ABC
from dataclasses import dataclass
from server.ats.trees.common import (BaseTree, ResourceMappingNode, SequenceNode,
                                     TextNode, TreeWithOutputs, YamlNode)


@dataclass
class DebuggingNode(YamlNode):
    allow_direct_access: TextNode = None
    connection_protocol: TextNode = None


@dataclass
class SpecNode(YamlNode):
    @dataclass
    class KubernetesSpecNode(YamlNode):
        cpu: TextNode = None
        ram: TextNode = None

    @dataclass
    class AwsSpecNode(YamlNode):
        instance_type: TextNode = None

    @dataclass
    class AzureSpecNode(YamlNode):
        vm_size: TextNode = None

    azure: AzureSpecNode = None
    aws: AwsSpecNode = None
    kubernetes: KubernetesSpecNode = None


@dataclass
class IngressHealthCheckNode(YamlNode):
    healthy_threshold: TextNode = None
    interval: TextNode = None
    path: TextNode = None
    status_code: TextNode = None
    timeout: TextNode = None
    unhealthy_threshold = None

    def _get_field_mapping(self) -> {str: str}:
        return super()._get_field_mapping().update(
            {"healthy-threshold": "healthy_threshold",
             "status-code": "status_code",
             "unhealthy-threshold": "unhealthy_threshold"}
        )


@dataclass
class PortInfoNode(YamlNode):
    port: TextNode = None
    path: TextNode = None


@dataclass
class PortInfoInternalNode(PortInfoNode):
    ingress_healthcheck: IngressHealthCheckNode = None
    port_range: TextNode = None

    def _get_field_mapping(self) -> {str: str}:
        return super()._get_field_mapping().update(
            {"port-range": "port_range",
             "ingress-healthcheck": "ingress_healthcheck"}
        )


@dataclass
class ExternalPortInfoMappingNode(ResourceMappingNode):
    value: PortInfoNode = None


@dataclass
class InternalPortInfoMappingNode(ResourceMappingNode):
    value: PortInfoInternalNode = None


@dataclass
class InfrastructureNode(YamlNode):
    @dataclass
    class ComputeNode(YamlNode):
        spec: SpecNode = None

    @dataclass
    class ConnectivityNode(YamlNode):
        @dataclass
        class ExternalPortsSequenceNode(SequenceNode):
            node_type = ExternalPortInfoMappingNode

        @dataclass
        class InternalPortsSequenceNode(SequenceNode):
            node_type = InternalPortInfoMappingNode

        external: ExternalPortsSequenceNode = None
        internal: InternalPortsSequenceNode = None

    @dataclass
    class InfraPermissionsNode(YamlNode):
        @dataclass
        class InfraAwsPermissionsNode(YamlNode):
            iam_instance_profile: TextNode = None

        @dataclass
        class InfraAzurePermissionsNode(YamlNode):
            managed_identity_id: TextNode = None

        aws: InfraAwsPermissionsNode = None
        azure: InfraAzurePermissionsNode = None

    compute: ComputeNode = None
    connectivity: ConnectivityNode = None
    permissions: InfraPermissionsNode = None


@dataclass
class ConfigurationNode(YamlNode):
    @dataclass
    class InitializationNode(YamlNode):
        script: TextNode = None

    @dataclass
    class StartNode(InitializationNode):
        command: TextNode = None

    @dataclass
    class HealthcheckNode(InitializationNode):
        timeout: TextNode = None
        wait_for_ports: TextNode = None

    initialization: InitializationNode = None
    start: StartNode = None
    healthcheck: HealthcheckNode = None


@dataclass
class AmiImageNode(YamlNode):
    id: TextNode = None
    region: TextNode = None
    username: TextNode = None


@dataclass
class AzureImageProps(ABC):
    subscription_id: TextNode = None
    resource_group: TextNode = None
    image: TextNode = None


@dataclass
class AzureImageNode(YamlNode):
    @dataclass
    class AzureGalleryImageNode(AzureImageProps, YamlNode):
        shared_image_gallery: TextNode = None
        image_definition: TextNode = None
        image_version: TextNode = None

    @dataclass
    class AzureCustomImageNode(AzureImageProps, YamlNode):
        image: TextNode = None

    urn: TextNode = None
    username: TextNode = None
    custom_image: AzureCustomImageNode = None
    gallery: AzureGalleryImageNode = None
    custom: TextNode = None


@dataclass
class DockerImageNode(YamlNode):
    name: TextNode = None
    pull_secret: TextNode = None
    tag: TextNode = None
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
class SourceNode(YamlNode):
    @dataclass
    class ImageNode(YamlNode):
        ami: AmiSequenceNode = None
        azure_image: AzureSequenceNode = None
        docker_image: DockerImagesSequence = None

    image: ImageNode = None
    os_type: TextNode = None


@dataclass
class AppTree(TreeWithOutputs, BaseTree):
    configuration: ConfigurationNode = None
    source: SourceNode = None
    debugging: DebuggingNode = None
    infrastructure: InfrastructureNode = None
    # old syntax
    ostype: TextNode = None