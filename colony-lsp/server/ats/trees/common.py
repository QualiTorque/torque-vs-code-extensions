from abc import ABC
from dataclasses import dataclass, field
from typing import Any, List, Optional


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
class MappingNode(YamlNode):  # TODO: actually all colony nodes must inherit this
    key: YamlNode = None
    value: YamlNode = None
    allow_variable: bool = False

    def set_key(self, node: YamlNode = None):
        if node is None:
            key_class = self.__dataclass_fields__['key'].type
            self.key = key_class(parent=self)

        else:
            self.key = node

        return self.key

    def set_value(self, node: YamlNode = None):
        if node is None:
            value_class = self.__dataclass_fields__['value'].type
            self.value = value_class(parent=self)

        else:
            self.value = node

        return self.value


@dataclass
class MapNode(YamlNode):
    items: [MappingNode] = field(default_factory=list)


@dataclass
class InputNode(MappingNode):
    key: TextNode = None
    value: TextNode = None
    allow_variable = True


@dataclass
class InputsNode(YamlNode):
    """
    Node representing the list of inputs
    """
    inputs: List[InputNode] = field(default_factory=list)

    def add(self, input_node: InputNode = None):
        if input_node is None:
            input_node = InputNode(parent=self)

        self.inputs.append(input_node)
        return self.inputs[-1]


@dataclass
class BaseTree(YamlNode):
    inputs_node: InputsNode = field(init=False)
    kind: TextNode = None

    def _get_field_mapping(self) -> {str: str}:
        mapping = super()._get_field_mapping()
        mapping.update(
            {"inputs": "inputs_node"}
        )
        return mapping

    def __post_init__(self):
        self.inputs_node = InputsNode(parent=self)


@dataclass
class ResourceNode(YamlNode):
    id: TextNode = None
    inputs_node: Optional[InputsNode] = field(init=False)
    depends_on: List[YamlNode] = field(default_factory=dict)  # TODO: ideally depends_on must be a node

    def add_input(self, input: InputNode):
        self.inputs_node.add(input)
        return self.inputs_node.inputs[-1]

    def __post_init__(self):
        self.inputs_node = InputsNode(parent=self)


@dataclass
class ResourcesContainerNode(YamlNode):
    """
    Node representing the list of resources
    """
    nodes: List[ResourceNode] = field(default_factory=list)

    def add(self, resource: ResourceNode):
        self.nodes.append(resource)
        return self.nodes[-1]


@dataclass
class TreeWithOutputs(ABC):
    outputs: List[YamlNode] = field(default_factory=list)
