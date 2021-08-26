from server.ats.trees.common import (
    PropertyNode,
    ScalarMappingNode,
    ScalarMappingsSequence,
    ScalarNode,
)
from server.ats.trees.service import ServiceTree

simple = ServiceTree(
    start_pos=(0, 0),
    end_pos=(4, 15),
    errors=[],
    outputs=None,
    inputs_node=PropertyNode(
        start_pos=(1, 0),
        end_pos=(4, 0),
        errors=[],
        key=ScalarNode(
            start_pos=(1, 0), end_pos=(1, 6), errors=[], _text="inputs_node"
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
