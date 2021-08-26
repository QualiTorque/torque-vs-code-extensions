import os
from posixpath import dirname
from server.ats.trees.common import (
    PropertyNode,
    ScalarMappingNode,
    ScalarMappingsSequence,
    ScalarNode,
)
from server.ats.parser import Parser, ParserError
from server.ats.trees.app import AppTree
from server.ats.trees.blueprint import (
    BlueprintTree,
    ApplicationNode,
    ApplicationResourceNode,
)
from server.ats.trees.service import ServiceTree
from server.tests.unit import trees
from server.tests.unit.trees import demoapp_tree, azuresimple_bp_tree, sleep_srv_tree, no_indent

import unittest


class TestParser(unittest.TestCase):
    def setUp(self) -> None:
        self.test_dir = os.path.join((dirname(os.path.abspath(__file__))), "fixtures")

    def _get_content(self, resources_type: str, name: str):
        if resources_type not in ["blueprints", "services", "applications"]:
            raise ValueError

        filename = f"{name}.yaml"
        if resources_type == "blueprints":
            path = os.path.join(self.test_dir, resources_type, filename)

        else:
            path = os.path.join(self.test_dir, resources_type, name, filename)

        if not os.path.isfile(path):
            raise ValueError(f"Wrong blueprint repo path: {path}")

        with open(path, "r") as f:
            content = f.read()
            return content

    def test_parser_resolve_tree_by_kind(self):
        cls_map = {
            "application": AppTree,
            "blueprint": BlueprintTree,
            "TerraForm": ServiceTree,
        }

        first_line = "spec_version: 1"
        for k, v in cls_map.items():
            content = first_line + "\n" + f"kind: {k}"

            parser = Parser(content)
            self.assertIsInstance(parser.tree, v)

    def test_wrong_king_causes_exception(self):
        content = "kind: bblueprint"
        with self.assertRaises(ParserError):
            _ = Parser(content)

    def test_parse_blueprint(self):
        doc = self._get_content("blueprints", "azure-simple")
        parser = Parser(doc)
        tree = parser.parse()

        self.assertEqual(tree, azuresimple_bp_tree.tree)

    def test_parse_app(self):
        doc = self._get_content("applications", "demoapp-server")
        parser = Parser(doc)
        tree = parser.parse()

        self.assertEqual(tree, demoapp_tree.tree)

    def test_parse_service(self):
        doc = self._get_content("services", "sleep-2")
        parser = Parser(doc)
        tree = parser.parse()

        self.assertEqual(tree, sleep_srv_tree.tree)

    def test_simple_array_without_indent(self):
        doc = """kind: TerraForm
inputs:
- DURATION
- PATH
spec_version: 1"""
        parser = Parser(doc)
        tree = parser.parse()
        self.assertEqual(tree, no_indent.simple)
        self.assertEqual(tree.errors, [])
