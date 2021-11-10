from dataclasses import dataclass
from .common import (BaseTree, ObjectNode, TreeWithOutputs,
                     TextNode, ScalarNodesSequence, TextMappingSequence, ScalarNode)


@dataclass
class ModuleNode(ObjectNode):
    source: TextNode = None
    enable_auto_tagging: ScalarNode = None
    exclude_from_tagging: ScalarNodesSequence = None


@dataclass
class VariablesNode(ObjectNode):
    var_file: ScalarNode = None
    values: TextMappingSequence = None

    def get_values(self):
        return self._get_seq_nodes("values")


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
