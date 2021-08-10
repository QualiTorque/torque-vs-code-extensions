from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Optional, ClassVar


@dataclass
class YamlNode(ABC):
    start_pos: tuple = None
    end_pos: tuple = None
    parent: Optional[Any] = None  # TODO: must be Node, not any

    def _get_field_mapping(self) -> {str: str}:
        return {}

    def get_child(self, child_name: str):
        """Returns value of node attribute.
        If the value is None, creates a child of type
        specified in type annotations and returns it
        """
        attr = child_name if hasattr(self, child_name) else self._get_field_mapping().get(child_name, None)

        # attribute could not be found in both object itself and mapping table
        if attr is None:
            raise AttributeError(f"There is no attribute with name {child_name}")

        child = getattr(self, attr)

        # obj has not been instantiated yet
        if child is None:
            # Get type of the child according to its annotation
            child_cls = self.__dataclass_fields__.get(attr).type

            try:
                child = child_cls(parent=self)
                setattr(self, attr, child)
            except Exception as e:
                raise

        return child


@dataclass
# Could be extended by VariableNote (for $VAR), PathNode(for artifacts), DoubleQuoted, SingleQuoted etc
class TextNode(YamlNode):
    text: str = ""


@dataclass
class SequenceNode(YamlNode):
    node_type: ClassVar[type] = YamlNode

    nodes: [node_type] = field(default_factory=list)

    def add(self, node: node_type = None):
        if node is None:
            node = self.node_type(parent=self)

        self.nodes.append(node)

        return self.nodes[-1]


@dataclass
class TextNodesSequence(SequenceNode):
    """Container for simple text arrays
    like outputs, depends on """
    node_type = TextNode


@dataclass
class MappingNode(YamlNode):  # TODO: actually all torque nodes must inherit this
    key: YamlNode = None
    value: YamlNode = None
    allow_variable: bool = False

    def get_key(self):
        if self.key is None:
            key_class = self.__dataclass_fields__['key'].type
            self.key = key_class(parent=self)

        return self.key

    def get_value(self, expected_type: type = None):
        """Returns mapping value
        If value is None, it first will be initialized
        When value has Union typing annotation it will try to initialize it with provided expected_type
        If expected_type is not provided, first type from Union will be used"""
        if self.value is None:
            value_class = self.__dataclass_fields__['value'].type

            try:
                possible_types = value_class.__args__ # check if it's union

            except AttributeError:
                possible_types = None

            if expected_type is not None and expected_type != value_class:
                if possible_types and expected_type in possible_types:
                    value_class = expected_type
                else:
                    raise ValueError(f"Mapping value cannot be initiated with type '{expected_type}'")

            else:
                value_class = value_class if not possible_types else possible_types[0]

            self.value = value_class(parent=self)

        return self.value


@dataclass
class ResourceMappingNode(MappingNode):
    key: TextNode = None

    @property
    def id(self):
        return self.key


@dataclass
class TextMapping(MappingNode):
    key: TextNode = None
    value: TextNode = None


@dataclass
class TextMappingSequence(SequenceNode):
    node_type = TextMapping


@dataclass
class MapNode(YamlNode):
    items: [MappingNode] = field(default_factory=list)


@dataclass
class InputNode(MappingNode):
    key: TextNode = None
    value: TextNode = None
    allow_variable = True


@dataclass
class InputsNode(SequenceNode):
    """
    Node representing the list of inputs
    """
    node_type = InputNode


@dataclass
class BaseTree(YamlNode):
    inputs_node: InputsNode = None
    kind: TextNode = None
    spec_version: TextNode = None

    def _get_field_mapping(self) -> {str: str}:
        mapping = super()._get_field_mapping()
        mapping.update(
            {"inputs": "inputs_node"}
        )
        return mapping


@dataclass
class TreeWithOutputs(ABC):
    outputs: TextNodesSequence = None
