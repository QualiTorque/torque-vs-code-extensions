import unittest
from typing import Tuple
from unittest.mock import MagicMock

from pygls.lsp.types.basic_structures import Position, Range
from server.ats.trees.blueprint import (
    ApplicationNode,
    ApplicationResourceNode,
    BlueprintFullInputNode,
    BlueprintInputNode,
    BlueprintInputsSequence,
    BlueprintTree,
    ServiceNode,
    ServiceResourceNode,
)
from server.ats.trees.common import (
    BaseTree,
    PropertyNode,
    ScalarMappingNode,
    ScalarMappingsSequence,
    ScalarNode,
    ScalarNodesSequence,
    TextMapping,
    TextMappingSequence,
    TreeWithOutputs,
)
from trees import (
    azuresimple_bp_tree,
    demoapp_tree,
    sleep_srv_tree,
)
from server.validation.app_validator import AppValidationHandler
from server.validation.bp_validatior import BlueprintValidationHandler
from server.validation.common import ValidationHandler
from server.validation.factory import ValidatorFactory
from server.validation.srv_validator import ServiceValidationHandler


class TestValidationFactory(unittest.TestCase):
    def setUp(self) -> None:
        self.test_doc = MagicMock()

    def test_factory_returns_correct_validator(self):
        self.assertIsInstance(
            ValidatorFactory.get_validator(demoapp_tree.tree, self.test_doc),
            AppValidationHandler,
        )

        self.assertIsInstance(
            ValidatorFactory.get_validator(azuresimple_bp_tree.tree, self.test_doc),
            BlueprintValidationHandler,
        )

        self.assertIsInstance(
            ValidatorFactory.get_validator(sleep_srv_tree.tree, self.test_doc),
            ServiceValidationHandler,
        )

    def test_factory_raise_error(self):
        tree = BlueprintTree(
            kind=PropertyNode(
                key=ScalarNode(
                    start_pos=(0, 0), end_pos=(0, 4), errors=[], _text="kind"
                ),
                value=ScalarNode(
                    start_pos=(0, 6), end_pos=(0, 15), errors=[], _text="blueEprint"
                ),
            )
        )

        with self.assertRaises(ValueError):
            _ = ValidatorFactory.get_validator(tree, self.test_doc)


class TestValidationHandler(unittest.TestCase):
    def setUp(self) -> None:
        self.test_doc = MagicMock()

    @staticmethod
    def _get_range(start: Tuple[int, int], end: Tuple[int, int]):
        return Range(
            start=Position(line=start[0], character=start[1]),
            end=Position(line=end[0], character=end[1]),
        )

    def test_validate_inputs_duplicates(self):
        word = "PORT"

        tree = BaseTree(
            inputs_node=PropertyNode(
                key=ScalarNode(start_pos=(1, 0), end_pos=(1, 6), _text="inputs_node"),
                value=ScalarMappingsSequence(
                    nodes=[
                        ScalarMappingNode(
                            key=ScalarNode(
                                start_pos=(2, 4), end_pos=(2, 8), _text=word
                            ),
                            value=ScalarNode(
                                start_pos=(2, 10), end_pos=(2, 14), _text="3001"
                            ),
                        ),
                        ScalarMappingNode(
                            key=ScalarNode(
                                start_pos=(3, 4), end_pos=(3, 16), _text=word
                            ),
                            value=ScalarNode(
                                start_pos=(3, 18), end_pos=(3, 63), _text="3002"
                            ),
                        ),
                    ]
                ),
            ),
        )
        validator = ValidationHandler(tree, self.test_doc)
        validator._validate_no_duplicates_in_inputs()
        diags = validator._diagnostics

        for d in diags:
            self.assertEqual(d.message, f"Multiple declarations of input '{word}'")
        self.assertEqual(len(diags), 2)
        self.assertEqual(diags[0].range, self._get_range((2, 4), (2, 8)))
        self.assertEqual(diags[1].range, self._get_range((3, 4), (3, 16)))

    def test_validate_duplicates_in_outputs(self):
        word = "test"

        tree = TreeWithOutputs(
            outputs=PropertyNode(
                key=ScalarNode(_text="inputs_node"),
                value=ScalarNodesSequence(
                    nodes=[
                        ScalarNode(start_pos=(5, 2), end_pos=(5, 6), _text=word),
                        ScalarNode(start_pos=(6, 2), end_pos=(6, 6), _text=word),
                    ]
                ),
            )
        )
        validator = ValidationHandler(tree, self.test_doc)
        validator._validate_no_duplicates_in_outputs()
        diags = validator._diagnostics

        self.assertEqual(len(diags), 2)
        for d in diags:
            self.assertEqual(
                d.message,
                f"Multiple declarations of output '{word}'. Outputs are not case sensitive.",
            )
        self.assertEqual(diags[0].range, self._get_range((5, 2), (5, 6)))
        self.assertEqual(diags[1].range, self._get_range((6, 2), (6, 6)))


class TestBlueprintValidationHandler(TestValidationHandler):
    def test_validate_default_value_not_in_possible_values_list(self):
        wrong_value = "ba"

        tree = BlueprintTree(
            inputs_node=PropertyNode(
                key=ScalarNode(_text="inputs_node"),
                value=BlueprintInputsSequence(
                    nodes=[
                        BlueprintInputNode(
                            key=ScalarNode(_text="ABC"),
                            value=BlueprintFullInputNode(
                                display_style=None,
                                description=None,
                                default_value=PropertyNode(
                                    key=ScalarNode(
                                        _text="default_value",
                                        start_pos=(18, 6),
                                        end_pos=(18, 19)
                                    ),
                                    value=ScalarNode(
                                        _text=f"{wrong_value}",
                                        start_pos=(18, 21),
                                        end_pos=(18, 23)
                                    ),
                                ),
                                optional=None,
                                possible_values=PropertyNode(
                                    key=ScalarNode(_text="possible_values"),
                                    value=ScalarNodesSequence(
                                        nodes=[
                                            ScalarNode(_text="a"),
                                            ScalarNode(_text="b"),
                                        ]
                                    ),
                                ),
                            ),
                        ),
                    ]
                ),
            ),
        )
        validator = BlueprintValidationHandler(tree, self.test_doc)
        validator._validate_default_value_in_possible_values()
        self.assertEqual(len(validator._diagnostics), 1)
        d = validator._diagnostics[0]
        self.assertEqual(f"Default value '{wrong_value}' must be in the list of possible values", d.message)
        self.assertEqual(d.range, self._get_range((18, 21), (18, 23)))

        # check for none
        tree.inputs_node.nodes[0].value.default_value.value = None
        validator = BlueprintValidationHandler(tree, self.test_doc)
        validator._validate_default_value_in_possible_values()
        self.assertEqual(len(validator._diagnostics), 1)
        d = validator._diagnostics[0]
        self.assertEqual(f"The default value cannot be empty if possible_values are set", d.message)
        self.assertEqual(d.range, self._get_range((18, 6), (18, 19)))


    def test_validate_resources_have_inputs(self):
        tree = BlueprintTree(
            inputs_node=None,
            applications=PropertyNode(
                key=ScalarNode(_text="applications"),
                value=BlueprintTree.AppsSequence(
                    nodes=[
                        ApplicationNode(
                            key=ScalarNode(_text="azure-ubuntu"),
                            value=ApplicationResourceNode(
                                input_values=PropertyNode(
                                    key=ScalarNode(_text="input_values"),
                                    value=TextMappingSequence(
                                        nodes=[
                                            TextMapping(
                                                key=ScalarNode(
                                                    start_pos=(7, 10),
                                                    end_pos=(7, 23),
                                                    _text="instance_type",
                                                ),
                                                value=None,
                                            )
                                        ]
                                    ),
                                )
                            ),
                        )
                    ]
                ),
            ),
            services=PropertyNode(
                key=ScalarNode(_text="services"),
                value=BlueprintTree.ServicesSequence(
                    nodes=[
                        ServiceNode(
                            key=ScalarNode(
                                _text="sleep",
                            ),
                            value=ServiceResourceNode(
                                input_values=PropertyNode(
                                    key=ScalarNode(_text="input_values"),
                                    value=TextMappingSequence(
                                        nodes=[
                                            TextMapping(
                                                key=ScalarNode(
                                                    start_pos=(9, 10),
                                                    end_pos=(9, 15),
                                                    _text="seconds",
                                                ),
                                                value=None,
                                            )
                                        ]
                                    ),
                                )
                            ),
                        )
                    ]
                ),
            ),
        )
        validator = BlueprintValidationHandler(tree, self.test_doc)
        validator._validate_blueprint_resources_have_input_values()

        self.assertEqual(len(validator._diagnostics), 2)
        if validator._diagnostics:
            for d in validator._diagnostics:
                self.assertTrue(
                    d.message.endswith(
                        "input must have a value or a blueprint input "
                        "with the same name should be defined"
                    )
                )
                self.assertTrue(
                    d.range
                    in [
                        self._get_range((7, 10), (7, 23)),
                        self._get_range((9, 10), (9, 15)),
                    ]
                )
