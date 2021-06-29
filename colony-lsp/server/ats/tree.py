from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

@dataclass
class YamlNode(ABC):
    start: tuple = None
    end: tuple = None
    parent: Optional[Any] = None # TODO: must be Node, not any


@dataclass
class MappingNode(YamlNode):
    key: YamlNode = None
    

@dataclass
class InputNode(YamlNode):
    name: str = None
    # value: Union[Var, String]
    value: Optional[str] = None
    allow_variable: bool = False

@dataclass
class InputsNode(YamlNode):
    """
    Node representing the list of inputs
    """

    inputs: List[InputNode] = field(default_factory=list)

    def add(self, input: InputNode):
        self.inputs.append(input)
        return self.inputs[-1]

@dataclass
class ApplicationNode(YamlNode):
    name: str = None
    key: YamlNode = YamlNode() # store key position
    inputs_node: Optional[InputsNode] = field(init=False)
    depends_on: Dict[str, YamlNode] = field(default_factory=dict) # TODO: ideally depends_on must be a node

    def add_input(self, input: InputNode):
        self.inputs_node.add(input)
        return self.inputs_node.inputs[-1]

    def __post_init__(self):
        self.inputs_node = InputsNode(parent=self)

@dataclass
class ApplicationsNode(YamlNode):
    """
    Node representing the list of apps
    """
    apps: List[ApplicationNode] = field(default_factory=list)

    def add(self, app: ApplicationNode):
        self.apps.append(app)
        return self.apps[-1]

@dataclass
class ColonyTree:
    inputs_node: Optional[InputsNode] = field(init=False)

    def __post_init__(self):
        self.inputs_node = InputsNode(parent=self)

@dataclass
class BlueprintTree(ColonyTree):
    apps_node: Optional[ApplicationsNode] = None

@dataclass
class AppTree(ColonyTree):
    pass