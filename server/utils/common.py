import logging
import os
import pathlib
from typing import List, Optional, Tuple

from pygls.lsp import types
from pygls.workspace import Document, position_from_utf16
from server.ats.parser import Parser, ParserError
from server.ats.trees.common import (
    BaseTree,
    MappingNode,
    Position,
    TextNode,
    YamlNode,
)
from server.utils.yaml_utils import format_yaml


class ResourcesManager:
    cache = None
    resource_folder = ""
    resource_type = ""

    @staticmethod
    def build_completion_text(resource_name: str, resource_tree: BaseTree) -> str:
        output = f"- {resource_name}:\n"
        inputs = resource_tree.get_inputs()
        if inputs:
            output += "    input_values:\n"
            for input_node in inputs:
                if input_node.value:
                    output += (
                        f"      - {input_node.key.text}: {input_node.value.text}\n"
                    )
                else:
                    output += f"      - {input_node.key.text}: \n"
        return output

    @classmethod
    def load_res_details(cls, resource_name: str, resource_source: str):
        resource_tree = None
        output = None
        try:
            resource_tree = Parser(document=resource_source).parse()
            output = cls.build_completion_text(resource_name, resource_tree)
        except ParserError as e:
            logging.warning(
                f"Unable to load {cls.resource_type} '{resource_name}.yaml' due to error: {e.message}"
            )
        except Exception as e:
            logging.warning(
                f"Unable to load {cls.resource_type} '{resource_name}.yaml' due to error: {str(e)}"
            )

        cls.cache[resource_name] = {
            "tree": resource_tree,
            "completion": format_yaml(output) if output else None,
        }

    @classmethod
    def reload_resource_details(cls, resource_name, resource_source):
        if cls.cache:  # if there is already a cache, add this file
            cls.load_res_details(resource_name, resource_source)

    @classmethod
    def remove_resource_details(cls, resource_name):
        if cls.cache:  # if there is already a cache, remove this file
            if resource_name in cls.cache:
                cls.cache.pop(resource_name)

    @classmethod
    def get_available_resources(cls, root_folder: str = None):
        if cls.cache:
            return cls.cache
        else:
            if root_folder:
                resources_path = os.path.join(root_folder, cls.resource_folder)
                if os.path.exists(resources_path):
                    for folder in os.listdir(resources_path):
                        res_dir = os.path.join(resources_path, folder)
                        if os.path.isdir(res_dir):
                            files = os.listdir(res_dir)
                            if f"{folder}.yaml" in files:
                                f = open(os.path.join(res_dir, f"{folder}.yaml"), "r")
                                source = f.read()
                                cls.load_res_details(folder, source)

                return cls.cache
            else:
                return None

    @classmethod
    def get_available_resources_names(cls):
        if cls.cache:
            return list(cls.cache.keys())
        else:
            return []

    @classmethod
    def get_inputs(cls, resource_name):
        if resource_name in cls.cache:
            resource_tree = cls.cache[resource_name]["tree"]
            if resource_tree and resource_tree.inputs_node:
                inputs = {}
                for input_node in resource_tree.get_inputs():
                    inputs[input_node.key.text] = (
                        input_node.value.text if input_node.value else None
                    )
                return inputs

        return {}

    @classmethod
    def get_outputs(cls, resource_name):
        if resource_name in cls.cache:
            res_tree = cls.cache[resource_name]["tree"]
            outputs = [out.text for out in res_tree.get_outputs()]
            return outputs

        return []


class Visitor:
    def __init__(self, cursor_position: types.Position):
        self.found_node = None
        self.cursor_position = Position(
            line=cursor_position.line, col=cursor_position.character
        )

    def visit_node(self, node: YamlNode):
        start = Position(node.start_pos[0], node.start_pos[1])
        end = Position(node.end_pos[0], node.end_pos[1])

        if start <= self.cursor_position <= end:
            self.found_node = node
            return True

        return False


def get_path_to_pos(tree: BaseTree, pos: Position) -> List[YamlNode]:
    v = Visitor(cursor_position=pos)
    tree.accept(visitor=v)

    if not v.found_node:
        return []

    path: List[YamlNode] = []
    node = v.found_node
    while node:
        path.insert(0, node)
        node = node.parent
    return path


def is_var_allowed(tree: BaseTree, pos: Position) -> bool:
    path = get_path_to_pos(tree, pos)

    if not path:
        return False

    node = path[-1]

    if isinstance(node, MappingNode):
        is_var = node.allow_vars
        if node.value is None and node.key and is_var:
            return True
    elif isinstance(node, TextNode):
        return node.allow_vars

    return False


def get_parent_node(tree: BaseTree, pos: Position):
    path = get_path_to_pos(tree, pos)

    if not path:
        return None

    while path:
        node = path.pop()
        if node.parent is None:
            break
        if (
            node.parent.start_pos[0] < pos.line
            and node.parent.start_pos[1] < pos.character
        ):
            return node.parent

    return None


def get_parent_node_text(tree: BaseTree, pos: Position):
    parent_node = get_parent_node(tree, pos)
    if parent_node and hasattr(parent_node, "text"):
        return parent_node.text
    else:
        return ""


def get_line_before_position(document: Document, position: types.Position):
    lines = document.lines
    if position.line >= len(lines):
        return None

    row, col = position_from_utf16(lines, position)
    line = lines[row]
    return line[:col]


def preceding_words(
    document: Document, position: types.Position
) -> Optional[Tuple[str, str]]:
    """
    Get the word under the cursor returning the start and end positions.
    """
    line = get_line_before_position(document, position)
    try:
        word = line.strip().split()[-2:]
        return word
    except ValueError:
        return None


def get_repo_root_path(path: str) -> str:
    full_path = pathlib.Path(path).absolute()
    if full_path.parents[0].name == "blueprints":
        return full_path.parents[1].absolute().as_posix()

    elif full_path.parents[1].name in ["services", "applications"]:
        return full_path.parents[2].absolute().as_posix()

    else:
        raise ValueError(
            f"Wrong document path of blueprint file: {full_path.as_posix()}"
        )
