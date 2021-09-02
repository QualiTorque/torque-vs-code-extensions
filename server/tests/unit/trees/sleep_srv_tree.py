from server.ats.trees.common import (
    PropertyNode,
    ScalarMappingNode,
    ScalarMappingsSequence,
    ScalarNode,
    ScalarNodesSequence,
    TextMapping,
    TextMappingSequence,
    TextNode,
)
from server.ats.trees.service import (
    ModuleNode,
    PermissionsNode,
    ServiceTree,
    VariablesNode,
)

tree = ServiceTree(
    start_pos=(0, 0),
    end_pos=(22, 0),
    errors=[],
    outputs=PropertyNode(
        start_pos=(6, 0),
        end_pos=(9, 0),
        errors=[],
        key=ScalarNode(start_pos=(6, 0), end_pos=(6, 7), errors=[], _text="outputs"),
        value=ScalarNodesSequence(
            start_pos=(7, 4),
            end_pos=(9, 0),
            errors=[],
            nodes=[
                ScalarNode(
                    start_pos=(7, 4), end_pos=(7, 12), errors=[], _text="hostname"
                )
            ],
        ),
    ),
    inputs_node=PropertyNode(
        start_pos=(3, 0),
        end_pos=(6, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(3, 0), end_pos=(3, 6), errors=[], _text="inputs_node"
        ),
        value=ScalarMappingsSequence(
            start_pos=(4, 2),
            end_pos=(6, 0),
            errors=[],
            nodes=[
                ScalarMappingNode(
                    start_pos=(4, 4),
                    end_pos=(4, 12),
                    errors=[],
                    key=ScalarNode(
                        start_pos=(4, 4), end_pos=(4, 12), errors=[], _text="DURATION"
                    ),
                    value=None,
                )
            ],
        ),
    ),
    kind=PropertyNode(
        start_pos=(1, 0),
        end_pos=(3, 0),
        errors=[],
        key=ScalarNode(start_pos=(1, 0), end_pos=(1, 4), errors=[], _text="kind"),
        value=ScalarNode(
            start_pos=(1, 6), end_pos=(1, 15), errors=[], _text="TerraForm"
        ),
    ),
    spec_version=PropertyNode(
        start_pos=(0, 0),
        end_pos=(1, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(0, 0), end_pos=(0, 12), errors=[], _text="spec_version"
        ),
        value=ScalarNode(start_pos=(0, 14), end_pos=(0, 15), errors=[], _text="1"),
    ),
    module=PropertyNode(
        start_pos=(9, 0),
        end_pos=(12, 0),
        errors=[],
        key=ScalarNode(start_pos=(9, 0), end_pos=(9, 6), errors=[], _text="module"),
        value=ModuleNode(
            start_pos=(10, 2),
            end_pos=(12, 0),
            errors=[],
            source=PropertyNode(
                start_pos=(10, 2),
                end_pos=(12, 0),
                errors=[],
                key=ScalarNode(
                    start_pos=(10, 2), end_pos=(10, 8), errors=[], _text="source"
                ),
                value=TextNode(
                    start_pos=(10, 10),
                    end_pos=(10, 65),
                    errors=[],
                    _text="github.com/amiros89/terraform-modules/terraform/sleep-2",
                ),
            ),
            enable_auto_tagging=None,
            exclude_from_tagging=None,
        ),
    ),
    terraform_version=PropertyNode(
        start_pos=(12, 0),
        end_pos=(14, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(12, 0), end_pos=(12, 17), errors=[], _text="terraform_version"
        ),
        value=TextNode(
            start_pos=(12, 19), end_pos=(12, 26), errors=[], _text="0.11.11"
        ),
    ),
    variables=PropertyNode(
        start_pos=(14, 0),
        end_pos=(18, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(14, 0), end_pos=(14, 9), errors=[], _text="variables"
        ),
        value=VariablesNode(
            start_pos=(15, 2),
            end_pos=(18, 0),
            errors=[],
            var_file=None,
            values=PropertyNode(
                start_pos=(15, 2),
                end_pos=(18, 0),
                errors=[],
                key=ScalarNode(
                    start_pos=(15, 2), end_pos=(15, 8), errors=[], _text="values"
                ),
                value=TextMappingSequence(
                    start_pos=(16, 4),
                    end_pos=(18, 0),
                    errors=[],
                    nodes=[
                        TextMapping(
                            start_pos=(16, 6),
                            end_pos=(18, 0),
                            errors=[],
                            key=ScalarNode(
                                start_pos=(16, 6),
                                end_pos=(16, 14),
                                errors=[],
                                _text="DURATION",
                            ),
                            value=TextNode(
                                start_pos=(16, 16),
                                end_pos=(16, 25),
                                errors=[],
                                _text="$DURATION",
                            ),
                        )
                    ],
                ),
            ),
        ),
    ),
    permissions=PropertyNode(
        start_pos=(18, 0),
        end_pos=(22, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(18, 0), end_pos=(18, 11), errors=[], _text="permissions"
        ),
        value=PermissionsNode(
            start_pos=(19, 2),
            end_pos=(22, 0),
            errors=[],
            azure=None,
            aws=PropertyNode(
                start_pos=(19, 2),
                end_pos=(22, 0),
                errors=[],
                key=ScalarNode(
                    start_pos=(19, 2), end_pos=(19, 5), errors=[], _text="aws"
                ),
                value=PermissionsNode.AwsPermissionsNode(
                    start_pos=(20, 4),
                    end_pos=(22, 0),
                    errors=[],
                    role_arn=PropertyNode(
                        start_pos=(20, 4),
                        end_pos=(21, 4),
                        errors=[],
                        key=ScalarNode(
                            start_pos=(20, 4),
                            end_pos=(20, 12),
                            errors=[],
                            _text="role_arn",
                        ),
                        value=TextNode(
                            start_pos=(20, 14),
                            end_pos=(20, 29),
                            errors=[],
                            _text="PowerUserAccess",
                        ),
                    ),
                    external_id=PropertyNode(
                        start_pos=(21, 4),
                        end_pos=(22, 0),
                        errors=[],
                        key=ScalarNode(
                            start_pos=(21, 4),
                            end_pos=(21, 15),
                            errors=[],
                            _text="external_id",
                        ),
                        value=TextNode(
                            start_pos=(21, 17),
                            end_pos=(21, 25),
                            errors=[],
                            _text="torque",
                        ),
                    ),
                ),
            ),
        ),
    ),
    tfvars_file=None,
)
