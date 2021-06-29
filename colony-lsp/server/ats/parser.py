from abc import ABC
from dataclasses import dataclass, field
from server.ats.tree import *
from typing import Any, Dict, Generator, List, Optional, Tuple
import yaml
from yaml import nodes
from yaml.parser import Parser
from yaml.tokens import BlockEndToken, BlockEntryToken, BlockMappingStartToken, BlockSequenceStartToken, KeyToken, ScalarToken, ValueToken


class Parser:
    def __init__(self, document) -> None:
        self.document = document

    def parse(self):
        pass

    #inputs processing is the same for apps and blueprints
    def _process_inputs(self, data: Generator, inputs_node: InputsNode) -> None:
        starting_token = next(data)
        tokens_stack = []
        extended_declare = False
        inputs_without_ident = False
        
        if isinstance(starting_token, BlockSequenceStartToken):
            tokens_stack.append(starting_token)

        # a special case when inputs are listed without indentation
        elif isinstance(starting_token, BlockEntryToken):
            inputs_without_ident = True
            tokens_stack.append(starting_token)

        else:
            raise ValueError("Starting token is not correct")

        while tokens_stack or inputs_without_ident:
            token = next(data)
            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if isinstance(token, BlockEntryToken): # dash ("-") symbol
                tokens_stack.append(token)
                continue

            # input without default value at all:
            if isinstance(token, ScalarToken) and isinstance(tokens_stack[-1], BlockEntryToken):
                input_node = InputNode(start=token_start, end=token_end, parent=inputs_node)
                input_node.key = TextNode(start=token_start, end=token_end, parent=input_node, text=token.value)

                inputs_node.add(input_node)
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

            # stack is empty. in case inputs do not have indentation
            # it means list has ended 
            if isinstance(token, KeyToken) and not tokens_stack:
                inputs_without_ident = False
                continue

            if isinstance(token, (KeyToken, ValueToken)) and not extended_declare:
                tokens_stack.append(token)
                continue

            if isinstance(token, ScalarToken):
                if not extended_declare:
                    top = tokens_stack.pop()
                    # it's an input name
                    if isinstance(top, KeyToken):
                        inputs_node.inputs[-1].key = TextNode(
                            start=token_start,
                            end=token_end,
                            parent=inputs_node.inputs[-1],
                            text=token.value
                        )
                        inputs_node.inputs[-1].start = token_start

                    # it's a default value
                    if isinstance(top, ValueToken):
                        inputs_node.inputs[-1].value = TextNode(
                            start=token_start,
                            end=token_end,
                            parent=inputs_node.inputs[-1],
                            text=token.value
                        )
 
                else:
                    # for now ignore all input properties except 'default_value'
                    if not isinstance(tokens_stack[-1], ScalarToken):
                        tokens_stack.append(token)
                    else:
                        scalar = tokens_stack.pop()
                        if scalar.value == "default_value":
                            inputs_node.inputs[-1].value = TextNode(
                                start=token_start,
                                end=token_end,
                                parent=inputs_node.inputs[-1],
                                text=token.value
                            )

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


class AppParser(Parser):
    def __init__(self, document):
        super().__init__(document=document)
        self._tree = AppTree()

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

                self._tree.inputs_node = inputs

        return self._tree


class BlueprintParser(Parser):
    def __init__(self, document):
        super().__init__(document=document)
        self._tree = BlueprintTree()
        

    # TODO: processing of all sub-nodes must me merged to single method    
    def _process_apps(self, data: Generator, apps_node: ApplicationNode) -> None:
        starting_token = next(data)
        tokens_stack = []
        inside_app_declaration = False

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
                continue
            
            if isinstance(token, KeyToken) and not inside_app_declaration:
                continue

            if isinstance(token, ValueToken) and not inside_app_declaration:
                tokens_stack.append(token)
                continue

            if isinstance(token, BlockMappingStartToken):
                top = tokens_stack.pop()
                if isinstance(top, BlockEntryToken): # it means it is a beginning of app declaration
                    apps_node.add(ApplicationNode(parent=apps_node, start=token_start))
                if isinstance(top, ValueToken): # internal properties of app
                    inside_app_declaration = True

                tokens_stack.append(token)

            if (isinstance(token, KeyToken) or isinstance(token, ValueToken)) and inside_app_declaration:
                tokens_stack.append(token)
                continue

            if isinstance(token, ScalarToken):
                if not inside_app_declaration:
                # we are at the beginning of app declaration
                    apps_node.apps[-1].name = token.value
                    apps_node.apps[-1].key = YamlNode(start=token_start, end=token_end)

                else:
                    top = tokens_stack.pop()
                    if token.value == "input_values":
                        inputs = InputsNode(start=token_start, parent=apps_node.apps[-1])

                        # ignore next "valueToken"
                        next(data)
                        self._process_inputs(data=data, inputs_node=inputs)
                        apps_node.apps[-1].inputs_node = inputs

                    # TODO: dirty handling. refactor
                    if token.value == "target" or token.value == "instances": 
                        # do nothing for now
                        next(data) # skip 
                        next(data)

                    if token.value == "depends_on":
                        
                        while not isinstance(token, BlockEndToken):
                            token = next(data)
                            if isinstance(token, ScalarToken):
                                apps_node.apps[-1].depends_on[token.value] = YamlNode(
                                    start=(token.start_mark.line, token.start_mark.column),
                                    end=(token.end_mark.line, token.end_mark.column)
                                )
                        continue
                     
            if isinstance(token, BlockEndToken):
                top = tokens_stack.pop() 
                if isinstance(top, BlockSequenceStartToken):
                    # now we have the end of applications block
                    apps_node.end = token_end

                elif isinstance(top, BlockMappingStartToken):
                    if inside_app_declaration:
                        inside_app_declaration = False
                    else:                       
                        apps_node.apps[-1].end = token_start

                else:
                    raise ValueError("Wrong structure of applications block")
            
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
            
            if isinstance(token, ScalarToken) and token.value == "applications":
                apps = ApplicationsNode(start=token_start, parent=self._tree)

                try:
                    # first we need to skip ValueToken
                    next(tokens)

                    self._process_apps(tokens, apps)
                except ValueError:
                    print("error during apps processing")
                    pass

                self._tree.apps_node = apps
            
            if isinstance(token, ScalarToken) and token.value == "inputs":
                inputs = InputsNode(start=token_start, parent=self._tree)
                try:
                    # first we need to skip ValueToken
                    next(tokens)

                    self._process_inputs(tokens, inputs)
                except ValueError:
                    print("error during inputs processing")
                    pass

                self._tree.inputs_node = inputs

        return self._tree
