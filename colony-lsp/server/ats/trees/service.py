from dataclasses import dataclass
from server.ats.trees.common import (BaseTree, TreeWithOutputs, YamlNode,
                                     TextNode, ScalarNodesSequence, TextMappingSequence, ScalarNode)


@dataclass
class ModuleNode(YamlNode):
    source: TextNode = None
    exclude_from_tagging: ScalarNodesSequence = None


@dataclass
class VariablesNode(YamlNode):
    var_file: ScalarNode = None
    values: TextMappingSequence = None


@dataclass
class PermissionsNode(YamlNode):
    @dataclass
    class AzurePermissionsNode(YamlNode):
        managed_identity_id: TextNode = None

    @dataclass
    class AwsPermissionsNode(YamlNode):
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
