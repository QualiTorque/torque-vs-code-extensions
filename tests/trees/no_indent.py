from server.ats.trees.app import (
    AmiImageNode,
    AmiSequenceNode,
    AppTree,
    DockerImageNode,
    DockerImagesSequence,
    SourceNode,
)
from server.ats.trees.blueprint import (
    ApplicationNode,
    ApplicationResourceNode,
    BlueprintTree,
)
from server.ats.trees.common import (
    NodeError,
    PropertyNode,
    ScalarMappingNode,
    ScalarMappingsSequence,
    ScalarNode,
    ScalarNodesSequence,
    TextNode,
)
from server.ats.trees.service import ServiceTree

##########################################################################
simple = ServiceTree(
    start_pos=(0, 0),
    end_pos=(4, 15),
    errors=[],
    outputs=None,
    inputs=PropertyNode(
        start_pos=(1, 0),
        end_pos=(4, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(1, 0), end_pos=(1, 6), errors=[], _text="inputs"
        ),
        value=ScalarMappingsSequence(
            start_pos=(2, 0),
            end_pos=(4, 0),
            errors=[],
            nodes=[
                ScalarMappingNode(
                    start_pos=(2, 2),
                    end_pos=(2, 10),
                    errors=[],
                    key=ScalarNode(
                        start_pos=(2, 2),
                        end_pos=(2, 10),
                        errors=[],
                        _text="DURATION",
                    ),
                    value=None,
                ),
                ScalarMappingNode(
                    start_pos=(3, 2),
                    end_pos=(3, 6),
                    errors=[],
                    key=ScalarNode(
                        start_pos=(3, 2),
                        end_pos=(3, 6),
                        errors=[],
                        _text="PATH",
                    ),
                    value=None,
                ),
            ],
        ),
    ),
    kind=PropertyNode(
        start_pos=(0, 0),
        end_pos=(1, 0),
        errors=[],
        key=ScalarNode(start_pos=(0, 0), end_pos=(0, 4), errors=[], _text="kind"),
        value=ScalarNode(
            start_pos=(0, 6), end_pos=(0, 15), errors=[], _text="TerraForm"
        ),
    ),
    spec_version=PropertyNode(
        start_pos=(4, 0),
        end_pos=(4, 15),
        errors=[],
        key=ScalarNode(
            start_pos=(4, 0),
            end_pos=(4, 12),
            errors=[],
            _text="spec_version",
        ),
        value=ScalarNode(start_pos=(4, 14), end_pos=(4, 15), errors=[], _text="1"),
    ),
    module=None,
    terraform_version=None,
    variables=None,
    permissions=None,
    tfvars_file=None,
)
##########################################################################
no_indent_colon = ServiceTree(
    start_pos=(0, 0),
    end_pos=(3, 15),
    errors=[],
    outputs=None,
    inputs=PropertyNode(
        start_pos=(1, 0),
        end_pos=(3, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(1, 0), end_pos=(1, 6), errors=[], _text="inputs"
        ),
        value=ScalarMappingsSequence(
            start_pos=(2, 0),
            end_pos=(3, 0),
            errors=[],
            nodes=[
                ScalarMappingNode(
                    start_pos=(2, 2),
                    end_pos=(3, 0),
                    errors=[],
                    key=ScalarNode(
                        start_pos=(2, 2), end_pos=(2, 10), errors=[], _text="DURATION"
                    ),
                    value=None,
                )
            ],
        ),
    ),
    kind=PropertyNode(
        start_pos=(0, 0),
        end_pos=(1, 0),
        errors=[],
        key=ScalarNode(start_pos=(0, 0), end_pos=(0, 4), errors=[], _text="kind"),
        value=ScalarNode(
            start_pos=(0, 6), end_pos=(0, 15), errors=[], _text="TerraForm"
        ),
    ),
    spec_version=PropertyNode(
        start_pos=(3, 0),
        end_pos=(3, 15),
        errors=[],
        key=ScalarNode(
            start_pos=(3, 0), end_pos=(3, 12), errors=[], _text="spec_version"
        ),
        value=ScalarNode(start_pos=(3, 14), end_pos=(3, 15), errors=[], _text="1"),
    ),
    module=None,
    terraform_version=None,
    variables=None,
    permissions=None,
    tfvars_file=None,
)
##########################################################################
no_indent_inside_no_indent = BlueprintTree(
    start_pos=(0, 0),
    end_pos=(9, 0),
    errors=[],
    inputs=None,
    kind=PropertyNode(
        start_pos=(0, 0),
        end_pos=(1, 0),
        errors=[],
        key=ScalarNode(start_pos=(0, 0), end_pos=(0, 4), errors=[], _text="kind"),
        value=ScalarNode(
            start_pos=(0, 6), end_pos=(0, 15), errors=[], _text="blueprint"
        ),
    ),
    spec_version=PropertyNode(
        start_pos=(8, 0),
        end_pos=(9, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(8, 0), end_pos=(8, 12), errors=[], _text="spec_version"
        ),
        value=ScalarNode(start_pos=(8, 14), end_pos=(8, 15), errors=[], _text="1"),
    ),
    applications=PropertyNode(
        start_pos=(1, 0),
        end_pos=(8, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(1, 0), end_pos=(1, 12), errors=[], _text="applications"
        ),
        value=BlueprintTree.AppsSequence(
            start_pos=(2, 0),
            end_pos=(8, 0),
            errors=[],
            nodes=[
                ApplicationNode(
                    start_pos=(2, 2),
                    end_pos=(4, 0),
                    errors=[],
                    key=ScalarNode(
                        start_pos=(2, 2), end_pos=(2, 11), errors=[], _text="basic-app"
                    ),
                    value=ApplicationResourceNode(
                        start_pos=(3, 4),
                        end_pos=(4, 0),
                        errors=[],
                        input_values=None,
                        depends_on=None,
                        target=None,
                        instances=PropertyNode(
                            start_pos=(3, 4),
                            end_pos=(4, 0),
                            errors=[],
                            key=ScalarNode(
                                start_pos=(3, 4),
                                end_pos=(3, 13),
                                errors=[],
                                _text="instances",
                            ),
                            value=TextNode(
                                start_pos=(3, 15), end_pos=(3, 16), errors=[], _text="1"
                            ),
                        ),
                    ),
                ),
                ApplicationNode(
                    start_pos=(4, 2),
                    end_pos=(8, 0),
                    errors=[],
                    key=ScalarNode(
                        start_pos=(4, 2),
                        end_pos=(4, 14),
                        errors=[],
                        _text="advanced-app",
                    ),
                    value=ApplicationResourceNode(
                        start_pos=(5, 4),
                        end_pos=(8, 0),
                        errors=[],
                        input_values=None,
                        depends_on=PropertyNode(
                            start_pos=(6, 4),
                            end_pos=(8, 0),
                            errors=[],
                            key=ScalarNode(
                                start_pos=(6, 4),
                                end_pos=(6, 14),
                                errors=[],
                                _text="depends_on",
                            ),
                            value=ScalarNodesSequence(
                                start_pos=(7, 6),
                                end_pos=(8, 0),
                                errors=[],
                                nodes=[
                                    ScalarNode(
                                        start_pos=(7, 6),
                                        end_pos=(7, 15),
                                        errors=[],
                                        _text="basic-app",
                                    )
                                ],
                            ),
                        ),
                        target=None,
                        instances=PropertyNode(
                            start_pos=(5, 4),
                            end_pos=(6, 4),
                            errors=[],
                            key=ScalarNode(
                                start_pos=(5, 4),
                                end_pos=(5, 13),
                                errors=[],
                                _text="instances",
                            ),
                            value=TextNode(
                                start_pos=(5, 15), end_pos=(5, 16), errors=[], _text="4"
                            ),
                        ),
                    ),
                ),
            ],
        ),
    ),
    services=None,
    artifacts=None,
    clouds=None,
    metadata=None,
    debugging=None,
    ingress=None,
    infrastructure=None,
    environmentType=None,
)
##########################################################################
empty_item_middle_no_indent = BlueprintTree(
    start_pos=(0, 0),
    end_pos=(7, 0),
    parent=None,
    errors=[
        NodeError(
            start_pos=(4, 0), end_pos=(4, 1), message="Element could not be empty"
        )
    ],
    inputs=None,
    kind=PropertyNode(
        start_pos=(0, 0),
        end_pos=(1, 0),
        parent=...,
        errors=[],
        key=ScalarNode(
            start_pos=(0, 0), end_pos=(0, 4), parent=..., errors=[], _text="kind"
        ),
        value=ScalarNode(
            start_pos=(0, 6),
            end_pos=(0, 15),
            parent=ScalarNode(
                start_pos=(0, 0), end_pos=(0, 4), parent=..., errors=[], _text="kind"
            ),
            errors=[],
            _text="blueprint",
        ),
    ),
    spec_version=PropertyNode(
        start_pos=(6, 0),
        end_pos=(7, 0),
        parent=...,
        errors=[],
        key=ScalarNode(
            start_pos=(6, 0),
            end_pos=(6, 12),
            parent=...,
            errors=[],
            _text="spec_version",
        ),
        value=ScalarNode(
            start_pos=(6, 14),
            end_pos=(6, 15),
            parent=ScalarNode(
                start_pos=(6, 0),
                end_pos=(6, 12),
                parent=...,
                errors=[],
                _text="spec_version",
            ),
            errors=[],
            _text="1",
        ),
    ),
    applications=PropertyNode(
        start_pos=(1, 0),
        end_pos=(6, 0),
        parent=...,
        errors=[
            NodeError(
                start_pos=(4, 0), end_pos=(4, 1), message="Element could not be empty"
            )
        ],
        key=ScalarNode(
            start_pos=(1, 0),
            end_pos=(1, 12),
            parent=...,
            errors=[
                NodeError(
                    start_pos=(4, 0),
                    end_pos=(4, 1),
                    message="Element could not be empty",
                )
            ],
            _text="applications",
        ),
        value=BlueprintTree.AppsSequence(
            start_pos=(2, 0),
            end_pos=(6, 0),
            parent=ScalarNode(
                start_pos=(1, 0),
                end_pos=(1, 12),
                parent=...,
                errors=[
                    NodeError(
                        start_pos=(4, 0),
                        end_pos=(4, 1),
                        message="Element could not be empty",
                    )
                ],
                _text="applications",
            ),
            errors=[
                NodeError(
                    start_pos=(4, 0),
                    end_pos=(4, 1),
                    message="Element could not be empty",
                )
            ],
            nodes=[
                ApplicationNode(
                    start_pos=(2, 2),
                    end_pos=(4, 0),
                    parent=...,
                    errors=[],
                    key=ScalarNode(
                        start_pos=(2, 2),
                        end_pos=(2, 11),
                        parent=...,
                        errors=[],
                        _text="basic-app",
                    ),
                    value=ApplicationResourceNode(
                        start_pos=(3, 4),
                        end_pos=(4, 0),
                        parent=ScalarNode(
                            start_pos=(2, 2),
                            end_pos=(2, 11),
                            parent=...,
                            errors=[],
                            _text="basic-app",
                        ),
                        errors=[],
                        input_values=None,
                        depends_on=None,
                        target=None,
                        instances=PropertyNode(
                            start_pos=(3, 4),
                            end_pos=(4, 0),
                            parent=...,
                            errors=[],
                            key=ScalarNode(
                                start_pos=(3, 4),
                                end_pos=(3, 13),
                                parent=...,
                                errors=[],
                                _text="instances",
                            ),
                            value=TextNode(
                                start_pos=(3, 15),
                                end_pos=(3, 16),
                                parent=ScalarNode(
                                    start_pos=(3, 4),
                                    end_pos=(3, 13),
                                    parent=...,
                                    errors=[],
                                    _text="instances",
                                ),
                                errors=[],
                                _text="1",
                            ),
                        ),
                    ),
                ),
                ApplicationNode(
                    start_pos=(5, 2),
                    end_pos=(6, 0),
                    parent=...,
                    errors=[],
                    key=ScalarNode(
                        start_pos=(5, 2),
                        end_pos=(5, 14),
                        parent=...,
                        errors=[],
                        _text="advanced-app",
                    ),
                    value=None,
                ),
            ],
        ),
    ),
    services=None,
    artifacts=None,
    clouds=None,
    metadata=None,
    debugging=None,
    ingress=None,
    infrastructure=None,
    environmentType=None,
)
##########################################################################
empty_item_end_no_indent = BlueprintTree(
    start_pos=(0, 0),
    end_pos=(7, 0),
    parent=None,
    errors=[
        NodeError(
            start_pos=(5, 0), end_pos=(5, 1), message="Element could not be empty"
        )
    ],
    inputs=None,
    kind=PropertyNode(
        start_pos=(0, 0),
        end_pos=(1, 0),
        parent=...,
        errors=[],
        key=ScalarNode(
            start_pos=(0, 0), end_pos=(0, 4), parent=..., errors=[], _text="kind"
        ),
        value=ScalarNode(
            start_pos=(0, 6),
            end_pos=(0, 15),
            parent=ScalarNode(
                start_pos=(0, 0), end_pos=(0, 4), parent=..., errors=[], _text="kind"
            ),
            errors=[],
            _text="blueprint",
        ),
    ),
    spec_version=PropertyNode(
        start_pos=(6, 0),
        end_pos=(7, 0),
        parent=...,
        errors=[],
        key=ScalarNode(
            start_pos=(6, 0),
            end_pos=(6, 12),
            parent=...,
            errors=[],
            _text="spec_version",
        ),
        value=ScalarNode(
            start_pos=(6, 14),
            end_pos=(6, 15),
            parent=ScalarNode(
                start_pos=(6, 0),
                end_pos=(6, 12),
                parent=...,
                errors=[],
                _text="spec_version",
            ),
            errors=[],
            _text="1",
        ),
    ),
    applications=PropertyNode(
        start_pos=(1, 0),
        end_pos=(6, 0),
        parent=...,
        errors=[
            NodeError(
                start_pos=(5, 0), end_pos=(5, 1), message="Element could not be empty"
            )
        ],
        key=ScalarNode(
            start_pos=(1, 0),
            end_pos=(1, 12),
            parent=...,
            errors=[
                NodeError(
                    start_pos=(5, 0),
                    end_pos=(5, 1),
                    message="Element could not be empty",
                )
            ],
            _text="applications",
        ),
        value=BlueprintTree.AppsSequence(
            start_pos=(2, 0),
            end_pos=(6, 0),
            parent=ScalarNode(
                start_pos=(1, 0),
                end_pos=(1, 12),
                parent=...,
                errors=[
                    NodeError(
                        start_pos=(5, 0),
                        end_pos=(5, 1),
                        message="Element could not be empty",
                    )
                ],
                _text="applications",
            ),
            errors=[
                NodeError(
                    start_pos=(5, 0),
                    end_pos=(5, 1),
                    message="Element could not be empty",
                )
            ],
            nodes=[
                ApplicationNode(
                    start_pos=(2, 2),
                    end_pos=(4, 0),
                    parent=...,
                    errors=[],
                    key=ScalarNode(
                        start_pos=(2, 2),
                        end_pos=(2, 11),
                        parent=...,
                        errors=[],
                        _text="basic-app",
                    ),
                    value=ApplicationResourceNode(
                        start_pos=(3, 4),
                        end_pos=(4, 0),
                        parent=ScalarNode(
                            start_pos=(2, 2),
                            end_pos=(2, 11),
                            parent=...,
                            errors=[],
                            _text="basic-app",
                        ),
                        errors=[],
                        input_values=None,
                        depends_on=None,
                        target=None,
                        instances=PropertyNode(
                            start_pos=(3, 4),
                            end_pos=(4, 0),
                            parent=...,
                            errors=[],
                            key=ScalarNode(
                                start_pos=(3, 4),
                                end_pos=(3, 13),
                                parent=...,
                                errors=[],
                                _text="instances",
                            ),
                            value=TextNode(
                                start_pos=(3, 15),
                                end_pos=(3, 16),
                                parent=ScalarNode(
                                    start_pos=(3, 4),
                                    end_pos=(3, 13),
                                    parent=...,
                                    errors=[],
                                    _text="instances",
                                ),
                                errors=[],
                                _text="1",
                            ),
                        ),
                    ),
                ),
                ApplicationNode(
                    start_pos=(4, 2),
                    end_pos=(5, 0),
                    parent=...,
                    errors=[],
                    key=ScalarNode(
                        start_pos=(4, 2),
                        end_pos=(4, 14),
                        parent=...,
                        errors=[],
                        _text="advanced-app",
                    ),
                    value=None,
                ),
            ],
        ),
    ),
    services=None,
    artifacts=None,
    clouds=None,
    metadata=None,
    debugging=None,
    ingress=None,
    infrastructure=None,
    environmentType=None,
)
##########################################################################
app_no_indent_deep = AppTree(
    start_pos=(0, 0),
    end_pos=(13, 0),
    errors=[
        NodeError(
            start_pos=(6, 4), end_pos=(6, 5), message="Element could not be empty"
        )
    ],
    inputs=None,
    kind=PropertyNode(
        start_pos=(11, 0),
        end_pos=(12, 0),
        errors=[],
        key=ScalarNode(start_pos=(11, 0), end_pos=(11, 4), errors=[], _text="kind"),
        value=ScalarNode(
            start_pos=(11, 6), end_pos=(11, 17), errors=[], _text="application"
        ),
    ),
    spec_version=PropertyNode(
        start_pos=(12, 0),
        end_pos=(13, 0),
        errors=[],
        key=ScalarNode(start_pos=(12, 0), end_pos=(12, 12), errors=[], _text="spec_version"),
        value=ScalarNode(start_pos=(12, 14), end_pos=(12, 15), errors=[], _text="1")
    ),
    outputs=None,
    configuration=None,
    source=PropertyNode(
        start_pos=(0, 0),
        end_pos=(11, 0),
        errors=[
            NodeError(
                start_pos=(6, 4), end_pos=(6, 5), message="Element could not be empty"
            )
        ],
        key=ScalarNode(
            start_pos=(0, 0),
            end_pos=(0, 6),
            errors=[
                NodeError(
                    start_pos=(6, 4),
                    end_pos=(6, 5),
                    message="Element could not be empty",
                )
            ],
            _text="source",
        ),
        value=SourceNode(
            start_pos=(1, 2),
            end_pos=(11, 0),
            errors=[
                NodeError(
                    start_pos=(6, 4),
                    end_pos=(6, 5),
                    message="Element could not be empty",
                )
            ],
            image=PropertyNode(
                start_pos=(1, 2),
                end_pos=(10, 2),
                errors=[
                    NodeError(
                        start_pos=(6, 4),
                        end_pos=(6, 5),
                        message="Element could not be empty",
                    )
                ],
                key=ScalarNode(
                    start_pos=(1, 2),
                    end_pos=(1, 7),
                    errors=[
                        NodeError(
                            start_pos=(6, 4),
                            end_pos=(6, 5),
                            message="Element could not be empty",
                        )
                    ],
                    _text="image",
                ),
                value=SourceNode.ImageNode(
                    start_pos=(2, 4),
                    end_pos=(10, 2),
                    errors=[
                        NodeError(
                            start_pos=(6, 4),
                            end_pos=(6, 5),
                            message="Element could not be empty",
                        )
                    ],
                    ami=PropertyNode(
                        start_pos=(2, 4),
                        end_pos=(7, 4),
                        errors=[
                            NodeError(
                                start_pos=(6, 4),
                                end_pos=(6, 5),
                                message="Element could not be empty",
                            )
                        ],
                        key=ScalarNode(
                            start_pos=(2, 4),
                            end_pos=(2, 7),
                            errors=[
                                NodeError(
                                    start_pos=(6, 4),
                                    end_pos=(6, 5),
                                    message="Element could not be empty",
                                )
                            ],
                            _text="ami",
                        ),
                        value=AmiSequenceNode(
                            start_pos=(3, 4),
                            end_pos=(7, 4),
                            errors=[
                                NodeError(
                                    start_pos=(6, 4),
                                    end_pos=(6, 5),
                                    message="Element could not be empty",
                                )
                            ],
                            nodes=[
                                AmiImageNode(
                                    start_pos=(3, 6),
                                    end_pos=(6, 4),
                                    errors=[],
                                    id=PropertyNode(
                                        start_pos=(3, 6),
                                        end_pos=(4, 6),
                                        errors=[],
                                        key=ScalarNode(
                                            start_pos=(3, 6),
                                            end_pos=(3, 8),
                                            errors=[],
                                            _text="id",
                                        ),
                                        value=TextNode(
                                            start_pos=(3, 10),
                                            end_pos=(3, 31),
                                            errors=[],
                                            _text="ami-034a66a2fdb1a734e",
                                        ),
                                    ),
                                    region=PropertyNode(
                                        start_pos=(4, 6),
                                        end_pos=(5, 6),
                                        errors=[],
                                        key=ScalarNode(
                                            start_pos=(4, 6),
                                            end_pos=(4, 12),
                                            errors=[],
                                            _text="region",
                                        ),
                                        value=ScalarNode(
                                            start_pos=(4, 14),
                                            end_pos=(4, 23),
                                            errors=[],
                                            _text="eu-west-1",
                                        ),
                                    ),
                                    username=PropertyNode(
                                        start_pos=(5, 6),
                                        end_pos=(6, 4),
                                        errors=[],
                                        key=ScalarNode(
                                            start_pos=(5, 6),
                                            end_pos=(5, 14),
                                            errors=[],
                                            _text="username",
                                        ),
                                        value=TextNode(
                                            start_pos=(5, 16),
                                            end_pos=(5, 22),
                                            errors=[],
                                            _text="ubuntu",
                                        ),
                                    ),
                                )
                            ],
                        ),
                    ),
                    azure_image=None,
                    docker_image=PropertyNode(
                        start_pos=(7, 4),
                        end_pos=(10, 2),
                        errors=[],
                        key=ScalarNode(
                            start_pos=(7, 4),
                            end_pos=(7, 16),
                            errors=[],
                            _text="docker_image",
                        ),
                        value=DockerImagesSequence(
                            start_pos=(8, 4),
                            end_pos=(10, 2),
                            errors=[],
                            nodes=[
                                DockerImageNode(
                                    start_pos=(8, 6),
                                    end_pos=(10, 2),
                                    errors=[],
                                    name=PropertyNode(
                                        start_pos=(8, 6),
                                        end_pos=(9, 6),
                                        errors=[],
                                        key=ScalarNode(
                                            start_pos=(8, 6),
                                            end_pos=(8, 10),
                                            errors=[],
                                            _text="name",
                                        ),
                                        value=TextNode(
                                            start_pos=(8, 12),
                                            end_pos=(8, 24),
                                            errors=[],
                                            _text="quali/ubuntu",
                                        ),
                                    ),
                                    pull_secret=None,
                                    tag=PropertyNode(
                                        start_pos=(9, 6),
                                        end_pos=(10, 2),
                                        errors=[],
                                        key=ScalarNode(
                                            start_pos=(9, 6),
                                            end_pos=(9, 9),
                                            errors=[],
                                            _text="tag",
                                        ),
                                        value=TextNode(
                                            start_pos=(9, 11),
                                            end_pos=(9, 26),
                                            errors=[],
                                            _text="elk624-python-2",
                                        ),
                                    ),
                                    username=None,
                                )
                            ],
                        ),
                    ),
                ),
            ),
            os_type=PropertyNode(
                start_pos=(10, 2),
                end_pos=(11, 0),
                errors=[],
                key=ScalarNode(
                    start_pos=(10, 2), end_pos=(10, 9), errors=[], _text="os_type"
                ),
                value=ScalarNode(
                    start_pos=(10, 11), end_pos=(10, 16), errors=[], _text="linux"
                ),
            ),
        ),
    ),
    debugging=None,
    infrastructure=None,
    ostype=None,
)
