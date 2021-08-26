import os
from posixpath import dirname
from server.ats.trees.common import BaseTree

from server.ats.parser import Parser, ParserError
from server.ats.trees.app import AppTree
from server.ats.trees.blueprint import BlueprintTree

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

    def _parse(self, doc: str) -> BaseTree:
        parser = Parser(doc)
        tree = parser.parse()
        return tree

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
        tree = self._parse(doc)

        self.assertEqual(tree, azuresimple_bp_tree.tree)

    def test_parse_app(self):
        doc = self._get_content("applications", "demoapp-server")
        tree = self._parse(doc)

        self.assertEqual(tree, demoapp_tree.tree)

    def test_parse_service(self):
        doc = self._get_content("services", "sleep-2")
        tree = self._parse(doc)

        self.assertEqual(tree, sleep_srv_tree.tree)

    def test_simple_array_without_indent_parsed_correctly(self):
        doc = """kind: TerraForm
inputs:
- DURATION
- PATH
spec_version: 1"""
        tree = self._parse(doc)
        self.assertEqual(tree, no_indent.simple)
        self.assertEqual(tree.errors, [])

    def test_no_value_in_list_without_indent_parsed_correctly(self):
        doc = """kind: TerraForm
inputs: 
- DURATION:
spec_version: 1"""
        tree = self._parse(doc)
        self.assertEqual(tree, no_indent.no_indent_colon)
        self.assertEqual(tree.errors, [])

    def test_no_indent_inside_no_indent_parsed_correctly(self):
        doc = """kind: blueprint
applications:
- basic-app:
    instances: 1
- advanced-app:
    instances: 4
    depends_on:
    - basic-app
spec_version: 1
"""
        tree = self._parse(doc)
        self.assertEqual(tree, no_indent.no_indent_inside_no_indent)
        self.assertEqual(tree.errors, [])
