import os
from posixpath import dirname
from server.ats.parser import Parser, ParserError
from server.ats.trees.app import AppTree
from server.ats.trees.blueprint import BlueprintTree, ApplicationNode, ApplicationResourceNode
from server.ats.trees.common import PropertyNode, ScalarNode, ScalarMappingsSequence, ScalarMappingNode, TextNode
from server.ats.trees.service import ServiceTree


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

        with open(path, 'r') as f:
            content = f.read()
            return content

    def test_parser_resolve_tree_by_kind(self):
        cls_map = {
            "application": AppTree,
            "blueprint": BlueprintTree,
            "TerraForm": ServiceTree
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
        doc = self._get_content('blueprints', 'azure-simple')
        parser = Parser(doc)
        tree = parser.parse()

        self.assertEqual(
            tree,
            BlueprintTree(start_pos=(0, 0), end_pos=(10, 0), errors=[], inputs_node=None,
                          kind=PropertyNode(start_pos=(0, 0),end_pos=(1, 0),errors=[],
                                            key=ScalarNode(
                                                start_pos=(0, 0),end_pos=(0, 4),errors=[],_text='kind'),
                                            value=ScalarNode(
                                                start_pos=(0, 6),end_pos=(0, 15),errors=[],_text='blueprint')),
                          spec_version=PropertyNode(start_pos=(6, 0),end_pos=(7, 0),errors=[],
                                                    key=ScalarNode(
                                                        start_pos=(6, 0),end_pos=(6, 12),errors=[],_text='spec_version'),
                                                    value=ScalarNode(
                                                        start_pos=(6, 14),end_pos=(6, 15),errors=[],_text='1')),
                          applications=PropertyNode(start_pos=(3, 0),end_pos=(6, 0),errors=[],
                                                    key=ScalarNode(start_pos=(3, 0),end_pos=(3, 12),errors=[],_text='applications'),
                                                    value=BlueprintTree.AppsSequence(
                                                        start_pos=(4, 2),end_pos=(6, 0),errors=[],nodes=[
                                                            ApplicationNode(
                                                                start_pos=(4, 4),end_pos=(6, 0),errors=[],
                                                                key=ScalarNode(start_pos=(4, 4),end_pos=(4, 16),errors=[],_text='azure-ubuntu'),
                                                                value=ApplicationResourceNode(
                                                                    start_pos=(5, 6),end_pos=(6, 0),errors=[],input_values=None,
                                                                    depends_on=None,target=None,
                                                                    instances=PropertyNode(
                                                                        start_pos=(5, 6),end_pos=(6, 0),errors=[],
                                                                        key=ScalarNode(
                                                                            start_pos=(5, 6),end_pos=(5, 15),errors=[],_text='instances'),
                                                                        value=TextNode(
                                                                            start_pos=(5, 17),end_pos=(5, 18),errors=[],_text='1'))))
                                                        ]
                                                    )),
                          services=None,
                          artifacts=None,
                          clouds=PropertyNode(start_pos=(1, 0),end_pos=(3, 0),errors=[],
                                              key=ScalarNode(start_pos=(1, 0),end_pos=(1, 6),errors=[],_text='clouds'),
                                              value=ScalarMappingsSequence(
                                                  start_pos=(2, 2),end_pos=(3, 0),errors=[],
                                                  nodes=[
                                                      ScalarMappingNode(
                                                          start_pos=(2, 4),end_pos=(3, 0),errors=[],
                                                          key=ScalarNode(start_pos=(2, 4),end_pos=(2, 17),errors=[],_text='azure-staging'),
                                                          value=ScalarNode(start_pos=(2, 19),end_pos=(2, 25),errors=[],_text='westus'))
                                                  ])),
                          metadata=None,
                          debugging=PropertyNode(start_pos=(8, 0),end_pos=(10, 0),errors=[],
                              key=ScalarNode(start_pos=(8, 0),end_pos=(8, 9),errors=[],_text='debugging'),
                              value=BlueprintTree.DebuggingNode(
                                  start_pos=(9, 2),end_pos=(10, 0),errors=[],
                                  bastion_availability=PropertyNode(
                                      start_pos=(9, 2),end_pos=(10, 0),errors=[],
                                      key=ScalarNode(start_pos=(9, 2),end_pos=(9, 22),errors=[],_text='bastion_availability'),
                                      value=ScalarNode(start_pos=(9, 24),end_pos=(9, 32),errors=[],_text='disabled')),
                                  direct_access=None,availability=None)),
                          ingress=None,
                          infrastructure=None,
                          environmentType=PropertyNode(
                              start_pos=(7, 0),end_pos=(8, 0),errors=[],
                              key=ScalarNode(start_pos=(7, 0),end_pos=(7, 15),errors=[],_text='environmentType'),
                              value=TextNode(start_pos=(7, 17),end_pos=(7, 24),errors=[],_text='sandbox')))
        )

