from abc import ABC
from dataclasses import dataclass, field
from typing import Any, Generator, List, Optional, Tuple
import yaml
from yaml.parser import Parser
from yaml.tokens import BlockEndToken, BlockEntryToken, BlockMappingStartToken, BlockSequenceStartToken, KeyToken, ScalarToken, ValueToken

@dataclass
class YamlNode(ABC):
    start: tuple = None
    end: tuple = None
    parent: Optional[Any] = None # TODO: must be Node, not any


@dataclass
class ApplicationNode(YamlNode):
    pass

@dataclass
class ApplicationsNode(YamlNode):
    """
    Node representing the list of apps
    """
    apps: List[ApplicationNode] = field(default_factory=list)

    def add(self, input: ApplicationNode):
        self.inputs.append(input)
        return self.apps[-1]

@dataclass
class InputNode(YamlNode):
    name: str = None
    default_value: Optional[str] = None


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
class BlueprintTree:
    applications: Optional[ApplicationsNode] = None
    inputs: Optional[InputsNode] = None

class BlueprintParser:
    def __init__(self, document) -> None:
        self.document = document
        self._tree = BlueprintTree()

    def _process_inputs(self, data: Generator, inputs_node: InputsNode) -> None:
        starting_token = next(data)
        tokens_stack = []
        extended_declare = False

        if isinstance(starting_token, BlockSequenceStartToken):
            tokens_stack.append(starting_token)

        else:
            raise ValueError("Starting token is not correct")

        while tokens_stack:
            token = next(data)
            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if isinstance(token, BlockEntryToken): # dash ("-") symbol
                tokens_stack.append(token)

            # input without default value at all:
            if isinstance(token, ScalarToken) and isinstance(tokens_stack[-1], BlockEntryToken):
                inputs_node.add(
                    InputNode(start=token_start, end=token_end, parent=inputs_node, name=token.value)
                )
                tokens_stack.pop()

            if isinstance(token, BlockMappingStartToken):
                top = tokens_stack.pop()
                if isinstance(top, BlockEntryToken): # it means it is a beginning of input declaration
                    inputs_node.add(InputNode(parent=inputs_node))
                
                # it is a beginning of full input declaration 
                # (could include 'display style' , 'description', ...)
                if isinstance(top, ValueToken):
                    extended_declare = True

                tokens_stack.append(token)

            if (isinstance(token, KeyToken) or isinstance(token, ValueToken)) and not extended_declare:
                tokens_stack.append(token)

            if isinstance(token, ScalarToken):
                if not extended_declare:
                    top = tokens_stack.pop()
                    # it's an input name
                    if isinstance(top, KeyToken):
                        inputs_node.inputs[-1].start = token_start
                        inputs_node.inputs[-1].name = token.value

                    # it's a default value
                    if isinstance(top, ValueToken):
                        inputs_node.inputs[-1].default_value = token.value
 
                else:
                    if not isinstance(tokens_stack[-1], ScalarToken):
                        tokens_stack.append(token)
                    else:
                        scalar = tokens_stack.pop()
                        if scalar.value == "default_value":
                            inputs_node.inputs[-1].default_value = token.value

            if isinstance(token, BlockEndToken):
                # on the top of a stack we always must have BlockMappingStartToken 
                # or BlockSequenceStartToken at this point
                top = tokens_stack.pop() 
                if isinstance(top, BlockSequenceStartToken):
                    # now we have the end of inputs block
                    inputs_node.end = token_end

                elif isinstance(top, BlockMappingStartToken):
                    if extended_declare:
                        extended_declare = False
                    else:                        
                        inputs_node.inputs[-1].end = token_start

                else:
                    raise ValueError("Wrong structure of input block")
            
    def parse(self):
        tokens = yaml.scan(self.document)
        token = None
        
        for token in tokens:
            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if isinstance(token, yaml.StreamStartToken):
                self._tree.start = token_start
            if isinstance(token, yaml.StreamEndToken):
                self._tree.end = token_end
            
            if isinstance(token, ScalarToken) and token.value == "inputs":
                inputs = InputsNode(start=token_start, parent=self._tree)
                try:
                    # first we need to skip ValueToken
                    next(tokens)

                    self._process_inputs(tokens, inputs)
                except ValueError:
                    print("error during inputs processing")
                    pass

                self._tree.inputs = inputs

        return self._tree
