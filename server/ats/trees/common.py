import re
from abc import ABC
from dataclasses import dataclass, field
from typing import Any, ClassVar, List, Optional, Tuple

from pygls.lsp import types


# TODO: refactor all the code to use this class
@dataclass
class Position:
    """
    Describes a position in the document
    """

    line: int
    col: int

    def __lt__(self, other):
        if not isinstance(other, Position):
            return NotImplementedError
        return self.line < other.line or (
            self.line == other.line and self.col < other.col
        )

    def __gt__(self, other):
        if not isinstance(other, Position):
            return NotImplemented
        return self.line > other.line or (
            self.line == other.line and self.col > other.col
        )

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    def to_lsp_pos(self) -> types.Position:
        """Convert this position to pygls' native Position type."""
        return types.Position(line=self.line, character=self.col)


@dataclass
class NodeError(Exception):
    start_pos: Tuple[int, int]
    end_pos: Tuple[int, int]
    message: str


@dataclass
class YamlNode(ABC):
    non_child_attributes: ClassVar[list] = ["start_pos", "end_pos", "parent", "errors"]

    start_pos: tuple = None
    end_pos: tuple = None
    parent: Optional[Any] = field(compare=False, default=None, repr=False)
    errors: List[NodeError] = field(default_factory=list)

    def add_error(self, error: NodeError) -> None:
        self.errors.append(error)
        if self.parent is not None:
            self.parent.add_error(error)

    def accept(self, visitor):
        visitor.visit_node(self)

    def get_children(self):
        return []

    def get_shortened_form_property(self):
        return None


@dataclass
class SequenceNode(YamlNode):
    node_type: ClassVar[type] = YamlNode

    nodes: List[node_type] = field(default_factory=list)

    def add(self, node: node_type = None):
        if node is None:
            node = self.node_type(parent=self)

        self.nodes.append(node)

        return self.nodes[-1]

    def get_children(self):
        return self.nodes


@dataclass
# Could be extended by VariableNote (for $VAR), PathNode(for artifacts), DoubleQuoted, SingleQuoted etc
class TextNode(YamlNode):
    allow_vars: ClassVar[bool] = True
    _text: str = ""
    style: str = None

    @property
    def text(self):
        return self._text

    @text.setter
    def text(self, v: str):
        try:
            self._validate(v)
        except NodeError as e:
            self.add_error(e)
        self._text = v

    def _validate(self, v: str):
        pass


class ScalarNode(TextNode):
    allow_vars = False

    def _validate(self, v: str):
        regex = re.compile("(\$\{.+?\}|^\$.+?$)|\{\{[^\{\}]*\}\}")
        # find first
        # m = regex.search(v)
        found = regex.finditer(v)

        for m in found:
            offset = m.span()
            self.add_error(NodeError(
                start_pos=(self.start_pos[0], self.start_pos[1] + offset[0]),
                end_pos=(self.end_pos[0], self.start_pos[1] + offset[1]),
                message="Variables are not allowed here",
            ))


@dataclass
class MappingNode(YamlNode):  # TODO: actually all torque nodes must inherit this
    key: ScalarNode = None
    value: YamlNode = None
    allow_vars: ClassVar[bool] = False

    def get_key(self):
        if self.key is None:
            key_class = self.__dataclass_fields__["key"].type
            self.key = key_class(parent=self)

        return self.key

    def get_value(self, expected_type: type = None):
        """Returns mapping value
        If value is None, it first will be initialized
        When value has Union typing annotation it will try to initialize it with provided expected_type
        If expected_type is not provided, first type from Union will be used"""
        if self.value is None:
            value_class = self.__dataclass_fields__["value"].type
            result_class = self._get_annotated_class(
                value_class=value_class, expected=expected_type
            )
            self.value = result_class(parent=self.key)

        return self.value

    def get_children(self):
        children = []
        if self.key:
            children.append(self.key)
        if self.value:
            children.append(self.value)

        return children

    def _get_annotated_class(self, value_class: type, expected: type = None) -> type:
        try:
            possible_types = value_class.__args__  # check if it's union

        except AttributeError:
            possible_types = None

        result_class = None
        if expected is not None and expected != value_class:
            if possible_types:
                for pt in possible_types:
                    if issubclass(pt, expected):
                        result_class = pt
                        break
            elif isinstance(value_class, type) and issubclass(value_class, expected):
                result_class = value_class
            else:
                raise ValueError(
                    f"Mapping value cannot be initiated with type '{expected}'"
                )

        else:
            result_class = value_class if not possible_types else possible_types[0]

        return result_class


# For now it's just a child of sequence node.
# will see in the future if we need to have a real map here
@dataclass
class MapNode(SequenceNode):
    node_type: ClassVar[type] = MappingNode

    def get_mapping_by_key(self, key: str ) -> MappingNode:
        for node in self.nodes:
            if node.key and node.key.text == key:
                return node
        return None 


class PropertyNode(MappingNode):
    @property
    def identifier(self):
        if self.key:
            return self.key.text

    def get_value(self, expected_type: type = None):
        if self.value is None:
            value_class = self.parent.__dataclass_fields__[self.identifier].type
            result_class = self._get_annotated_class(
                value_class=value_class, expected=expected_type
            )
            self.value = result_class(parent=self.key)

        return self.value

    def __getattr__(self, name: str) -> Any:
        if self.value is None:
            return None
        val = getattr(self.value, name, None)

        if val is not None:
            return val
        else:
            value_class = self.parent.__dataclass_fields__[self.identifier].type
            if name not in value_class.__dataclass_fields__:
                raise AttributeError(
                    f"Value of PropertyNode '{self.identifier}' does not not have attribute '{name}'"
                )

            return None


@dataclass
class ObjectNode(YamlNode, ABC):
    def _get_field_mapping(self) -> {str: str}:
        return {}

    def _check_attr(self, attr_name) -> str:
        attr = (
            attr_name
            if attr_name in self.__dict__
            else self._get_field_mapping().get(attr_name, None)
        )
        if attr is None:
            raise AttributeError(f"There is no attribute with name {attr_name}")

        return attr

    def __getattr__(self, attr_name) -> Any:
        attr = self._check_attr(attr_name)  
        return getattr(self, attr)


    def get_child(self, child_name: str):
        """Returns value of node attribute.
        If the value is None, creates a child of type
        specified in type annotations and returns it
        """
        attr = self._check_attr(child_name)

        child = getattr(self, attr)
        
        # obj has not been instantiated yet
        if child is None:
            child = PropertyNode(parent=self)
            child.get_key().text = attr

            # Get type of the child according to its annotation
            child_cls = self.__dataclass_fields__.get(attr).type

            if issubclass(child_cls, TextNode):
                child.allow_vars = child_cls.allow_vars
            try:
                setattr(self, attr, child)
            except Exception:
                raise

        return child

    def get_children(self):
        """Returns all child nodes. Nodes are actually
        attributes which are not excluded and do not equal None"""
        fields = vars(self)
        return [
            val
            for key, val in fields.items()
            if val and key not in self.non_child_attributes
        ]

    def _get_seq_nodes(self, property_name) -> List[Any]:
        if not hasattr(self, property_name):
            raise AttributeError

        if not issubclass(self.__dataclass_fields__[property_name].type, SequenceNode):
            return ValueError(f"Property '{property_name}' is not sequence")

        prop: PropertyNode = getattr(self, property_name, None)

        if prop is None or prop.value is None:
            return []

        seq: SequenceNode = prop.value
        return seq.nodes


@dataclass
class ScalarNodesSequence(SequenceNode):
    """
    Container for simple text arrays
    like outputs, depends on
    """

    node_type = ScalarNode


@dataclass
class TextNodesSequence(SequenceNode):
    node_type = TextNode


@dataclass
class ResourceMappingNode(MappingNode):
    key: ScalarNode = None

    @property
    def id(self):
        return self.key


@dataclass
class TextMapping(MappingNode):
    key: ScalarNode = None
    value: TextNode = None
    allow_vars = True


@dataclass
class TextMappingSequence(SequenceNode):
    node_type = TextMapping


@dataclass
class ScalarMappingNode(MappingNode):
    key: ScalarNode = None
    value: ScalarNode = None


@dataclass
class ScalarMappingsSequence(SequenceNode):
    node_type = ScalarMappingNode


@dataclass
class BaseTree(ObjectNode):
    inputs: ScalarMappingsSequence = None
    kind: ScalarNode = None
    spec_version: ScalarNode = None

    def get_inputs(self) -> List[MappingNode]:
        return self._get_seq_nodes("inputs")


@dataclass
class TreeWithOutputs(ObjectNode, ABC):
    outputs: ScalarNodesSequence = None

    def get_outputs(self) -> List[ScalarNode]:
        return self._get_seq_nodes("outputs")
