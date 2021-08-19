from dataclasses import dataclass
from server.ats.trees.common import (BaseTree, ObjectNode, TreeWithOutputs, YamlNode,
                                     TextNode, ScalarNodesSequence, TextMappingSequence, ScalarNode)


@dataclass
class ModuleNode(ObjectNode):
    source: TextNode = None
    exclude_from_tagging: ScalarNodesSequence = None


@dataclass
class VariablesNode(ObjectNode):
    var_file: ScalarNode = None
    values: TextMappingSequence = None


@dataclass
class PermissionsNode(ObjectNode):
    @dataclass
    class AzurePermissionsNode(ObjectNode):
        managed_identity_id: TextNode = None

    @dataclass
    class AwsPermissionsNode(ObjectNode):
        role_arn: TextNode = None
        external_id: TextNode = None

    azure: AzurePermissionsNode = None
    aws: AwsPermissionsNode = None


@dataclass
class ServiceTree(BaseTree, TreeWithOutputs):
    module: ModuleNode = None
    terraform_version: TextNode = None
    variables: VariablesNode = None
    permissions: PermissionsNode = None
    # old syntax
    tfvars_file: ScalarNode = None
