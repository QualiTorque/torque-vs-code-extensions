import os
from posixpath import dirname

from pygls.workspace import Document

from server.validation.app_validator import AppValidationHandler
from server.validation.bp_validatior import BlueprintValidationHandler
from server.validation.srv_validator import ServiceValidationHandler
from server.ats.trees.common import PropertyNode, ScalarNode

from server.ats.trees.blueprint import BlueprintTree
from server.validation.factory import ValidatorFactory

from server.tests.unit.trees import (
    demoapp_tree,
    azuresimple_bp_tree,
    sleep_srv_tree,
)

import unittest
from unittest.mock import MagicMock


class TestValidator(unittest.TestCase):
    # def setUp(self) -> None:
    #     self.test_dir = os.path.join((dirname(os.path.abspath(__file__))), "fixtures")
    def test_factory_returns_correct_validator(self):
        test_doc = MagicMock()
        self.assertIsInstance(
            ValidatorFactory.get_validator(demoapp_tree.tree, test_doc),
            AppValidationHandler,
        )

        self.assertIsInstance(
            ValidatorFactory.get_validator(azuresimple_bp_tree.tree, test_doc),
            BlueprintValidationHandler,
        )

        self.assertIsInstance(
            ValidatorFactory.get_validator(sleep_srv_tree.tree, test_doc),
            ServiceValidationHandler,
        )

    def test_factory_raise_error(self):
        test_doc = MagicMock()
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
            _ = ValidatorFactory.get_validator(tree, test_doc)
