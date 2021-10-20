from server.ats.trees.common import (
    NodeError,
    PropertyNode,
    ScalarNode,
)
from server.ats.trees.blueprint import (
    BlueprintTree,
)

no_child_simple = BlueprintTree(
    start_pos=(0, 0),
    end_pos=(3, 0),
    parent=None,
    errors=[
        NodeError(
            start_pos=(1, 0),
            end_pos=(1, 4),
            message="Parent node doesn't have child with name 'test'",
        )
    ],
    inputs_node=None,
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
        start_pos=(2, 0),
        end_pos=(3, 0),
        parent=...,
        errors=[],
        key=ScalarNode(
            start_pos=(2, 0),
            end_pos=(2, 12),
            parent=...,
            errors=[],
            _text="spec_version",
        ),
        value=ScalarNode(
            start_pos=(2, 14),
            end_pos=(2, 15),
            parent=ScalarNode(
                start_pos=(2, 0),
                end_pos=(2, 12),
                parent=...,
                errors=[],
                _text="spec_version",
            ),
            errors=[],
            _text="1",
        ),
    ),
    applications=None,
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
no_child_object = BlueprintTree(
    start_pos=(0, 0),
    end_pos=(7, 0),
    parent=None,
    errors=[
        NodeError(
            start_pos=(1, 0),
            end_pos=(1, 15),
            message="Parent node doesn't have child with name 'iInfrastructure'",
        )
    ],
    inputs_node=None,
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
    applications=None,
    services=None,
    artifacts=None,
    clouds=None,
    metadata=None,
    debugging=None,
    ingress=None,
    infrastructure=None,
    environmentType=None,
)
