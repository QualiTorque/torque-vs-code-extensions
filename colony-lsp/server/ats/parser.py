from abc import abstractmethod
from server.ats.tree import *
from typing import Generator, List
import yaml
from yaml.parser import Parser
from yaml.tokens import BlockEndToken, BlockEntryToken, BlockMappingStartToken, BlockSequenceStartToken, KeyToken, \
    ScalarToken, Token, ValueToken


class Parser(ABC):
    def __init__(self, document) -> None:
        self.document = document

    @abstractmethod
    def parse(self):
        pass

    @staticmethod
    def process_simple_array(data: Generator, container: List[TextNode], parent_node: YamlNode = None):
        token = next(data)
        if not isinstance(token, (BlockSequenceStartToken, BlockEntryToken)):
            raise ValueError("Wrong beginning of list block")

        while isinstance(token, (BlockSequenceStartToken, ScalarToken, BlockEntryToken)):
            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if isinstance(token, ScalarToken):
                node = TextNode(start=token_start, end=token_end, parent=parent_node, text=token.value)
                container.append(node)
            token = next(data)

        return None if isinstance(token, BlockEndToken) else token

    # inputs processing is the same for apps and blueprints
    def _process_inputs(self, data: Generator, inputs_node: InputsNode) -> Token:
        """
        Return None if inputs block has normal indentation
        or last processed token if there is no indent
        """
        starting_token = next(data)
        tokens_stack = []
        extended_declare = False
        no_indent = False

        if isinstance(starting_token, BlockSequenceStartToken):
            tokens_stack.append(starting_token)

        # a special case when inputs are listed without indentation
        elif isinstance(starting_token, BlockEntryToken):
            no_indent = True
            tokens_stack.append(starting_token)

        else:
            raise ValueError("Starting token is not correct")

        while tokens_stack or no_indent:
            token = next(data)
            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if isinstance(token, BlockEntryToken):  # dash ("-") symbol
                tokens_stack.append(token)
                continue

            # input without default value at all:
            if isinstance(token, ScalarToken) and isinstance(tokens_stack[-1], BlockEntryToken):
                input_node = InputNode(start=token_start, end=token_end, parent=inputs_node)
                input_node.key = TextNode(start=token_start, end=token_end, parent=input_node, text=token.value)

                inputs_node.add(input_node)
                tokens_stack.pop()
                continue

            if isinstance(token, BlockMappingStartToken):
                top = tokens_stack.pop()
                if isinstance(top, BlockEntryToken):  # it means it is a beginning of input declaration
                    inputs_node.add(InputNode(parent=inputs_node))

                # it is a beginning of full input declaration 
                # (could include 'display style' , 'description', ...)
                if isinstance(top, ValueToken):
                    extended_declare = True

                tokens_stack.append(token)

            # stack is empty. in case inputs do not have indentation
            # it means list has ended 
            if not tokens_stack and not isinstance(token, BlockEntryToken):
                # but last token taken from generator is not a part of inputs block
                # so return it back to calling code
                return token

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
                # last element in the list had a colon without value
                if isinstance(top, ValueToken):
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
                    raise ValueError("Wrong structure of inputs block")


class AppSrvParser(Parser):
    def parse(self):
        tokens = yaml.scan(self.document)

        for token in tokens:
            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if isinstance(token, yaml.StreamStartToken):
                self._tree.start = token_start
            if isinstance(token, yaml.StreamEndToken):
                self._tree.end = token_end

            if isinstance(token, ScalarToken):
                if token.value == "inputs":
                    inputs = InputsNode(start=token_start, parent=self._tree)
                    try:
                        # first we need to skip ValueToken
                        next(tokens)

                        self._process_inputs(tokens, inputs)
                    except ValueError:
                        print("error during inputs processing")
                        pass

                    self._tree.inputs_node = inputs

                if token.value == "outputs":
                    outputs_list: List[TextNode] = []
                    # first we need to skip ValueToken
                    next(tokens)
                    Parser.process_simple_array(tokens, outputs_list, self._tree)
                    self._tree.outputs = outputs_list

        return self._tree


class AppParser(AppSrvParser):
    def __init__(self, document):
        super().__init__(document=document)
        self._tree = AppTree()

    def parse(self):
        return super().parse()


class ServiceParser(AppSrvParser):
    def __init__(self, document):
        super().__init__(document=document)
        self._tree = ServiceTree()

    def parse(self):
        return super().parse()


class BlueprintParser(Parser):
    def __init__(self, document):
        super().__init__(document=document)
        self._tree = BlueprintTree()

    def _process_artifacts(self, data: Generator):
        starting_token = next(data)
        tokens_stack = []
        no_indent = False

        if isinstance(starting_token, BlockSequenceStartToken):
            tokens_stack.append(starting_token)

        # a special case when artifacts are listed without indentation
        elif isinstance(starting_token, BlockEntryToken):
            no_indent = True
            tokens_stack.append(starting_token)

        else:
            raise ValueError("Starting token is not correct")

        while tokens_stack or no_indent:
            token = next(data)
            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if isinstance(token, BlockEntryToken):  # dash ("-") symbol
                tokens_stack.append(token)
                continue

            # artifact without value
            if isinstance(token, ScalarToken) and isinstance(tokens_stack[-1], BlockEntryToken):
                self._tree.artifacts.append(
                    MappingNode(
                        start=token_start,
                        end=token_end,
                        parent=self._tree,
                    ))
                self._tree.artifacts[-1].key = TextNode(
                    start=token_start,
                    end=token_end,
                    text=token.value,
                    parent=self._tree.artifacts[-1]
                )

                tokens_stack.pop()
                continue

            if isinstance(token, BlockMappingStartToken):
                top = tokens_stack.pop()
                if isinstance(top, BlockEntryToken):  # it means it is a beginning of mapping
                    self._tree.artifacts.append(MappingNode(parent=self._tree))

                tokens_stack.append(token)
                continue

            # stack is empty. in case artifacts do not have indentation
            # it means list has ended 
            if not tokens_stack and not isinstance(token, BlockEntryToken):
                # but last token taken from generator is not a part of block
                # so return it back to calling code
                return token

            if isinstance(token, (KeyToken, ValueToken)):
                tokens_stack.append(token)
                continue

            if isinstance(token, ScalarToken):
                top = tokens_stack.pop()
                # it's an input name
                if isinstance(top, KeyToken):
                    self._tree.artifacts[-1].key = TextNode(
                        start=token_start,
                        end=token_end,
                        parent=self._tree,
                        text=token.value
                    )
                    self._tree.artifacts[-1].start = token_start

                # it's a default value
                if isinstance(top, ValueToken):
                    self._tree.artifacts[-1].value = TextNode(
                        start=token_start,
                        end=token_end,
                        parent=self._tree,
                        text=token.value
                    )

            if isinstance(token, BlockEndToken):
                # on the top of a stack we always must have BlockMappingStartToken 
                # or BlockSequenceStartToken at this point
                top = tokens_stack.pop()
                # last element in the list had a colon without value
                if isinstance(top, ValueToken):
                    top = tokens_stack.pop()
                if isinstance(top, BlockSequenceStartToken):
                    pass
                    # inputs_node.end = token_end

                elif isinstance(top, BlockMappingStartToken):
                    self._tree.artifacts[-1].end = token_start

                else:
                    raise ValueError("Wrong structure of artifacts block")

    # TODO: processing of all sub-nodes must me merged to single method    
    def _process_resources(self, data: Generator, container_node: ResourcesContainerNode, resources_name: str) -> None:
        if resources_name not in ["applications", "services"]:
            raise AttributeError("resources_type must be in ['applications', 'services']")

        resource_map = {
            "applications": ApplicationNode,
            "services": ServiceNode
        }

        starting_token = next(data)
        tokens_stack = []
        inside_declaration = False
        no_indent = False
        last_token = None

        if isinstance(starting_token, BlockSequenceStartToken):
            tokens_stack.append(starting_token)

        # a special case when artifacts are listed without indentation
        elif isinstance(starting_token, BlockEntryToken):
            no_indent = True
            tokens_stack.append(starting_token)

        else:
            raise ValueError("Starting token is not correct")

        while tokens_stack or no_indent:
            token = last_token or next(data)

            if last_token:
                last_token = None

            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if not tokens_stack and not isinstance(token, BlockEntryToken):
                # but last token taken from generator is not a part of inputs block
                # so return it back to calling code
                return token

            if isinstance(token, BlockEntryToken):  # dash ("-") symbol
                tokens_stack.append(token)
                continue

            if isinstance(token, ScalarToken) and isinstance(tokens_stack[-1], BlockEntryToken):
                res_node = resource_map[resources_name](
                    parent=container_node, start=token_start, end=token_end
                )
                res_node.id = TextNode(start=token_start, end=token_end, text=token.value)
                container_node.add(res_node)
                tokens_stack.pop()
                continue

            if isinstance(token, KeyToken) and not inside_declaration:
                continue

            if isinstance(token, ValueToken) and not inside_declaration:
                tokens_stack.append(token)
                continue

            if isinstance(token, BlockMappingStartToken):
                top = tokens_stack.pop()
                if isinstance(top, BlockEntryToken):  # it means it is a beginning of resource declaration
                    container_node.add(resource_map[resources_name](parent=container_node, start=token_start))
                if isinstance(top, ValueToken):  # internal properties of resource
                    inside_declaration = True

                tokens_stack.append(token)

            if (isinstance(token, KeyToken) or isinstance(token, ValueToken)) and inside_declaration:
                tokens_stack.append(token)
                continue

            if isinstance(token, ScalarToken):
                if not inside_declaration:
                    # we are at the beginning of app declaration
                    container_node.nodes[-1].id = TextNode(
                        start=token_start,
                        end=token_end,
                        parent=container_node.nodes[-1],
                        text=token.value
                    )

                else:
                    _ = tokens_stack.pop()
                    if token.value == "input_values":
                        inputs = InputsNode(start=token_start, parent=container_node.nodes[-1])

                        # ignore next "valueToken"
                        next(data)
                        last_token = self._process_inputs(data=data, inputs_node=inputs)
                        container_node.nodes[-1].inputs_node = inputs

                    elif token.value == "depends_on":
                        deps: List[TextNode] = []
                        next(data)
                        last_token = Parser.process_simple_array(data, deps, container_node.nodes[-1])
                        container_node.nodes[-1].depends_on = deps

                        continue

                    else:
                        if resources_name == "applications":
                            # TODO: add handling
                            if token.value == "target" or token.value == "instances":
                                pass
                        else:
                            pass

                        # do nothing for now
                        next(data)  # skip
                        next(data)

            if isinstance(token, BlockEndToken):
                top = tokens_stack.pop()
                # last element in the list had a colon without value
                if isinstance(top, ValueToken):
                    top = tokens_stack.pop()
                if isinstance(top, BlockSequenceStartToken):
                    # now we have the end of applications block
                    container_node.end = token_end

                elif isinstance(top, BlockMappingStartToken):
                    if inside_declaration:
                        inside_declaration = False
                    else:
                        container_node.nodes[-1].end = token_start
                else:
                    raise ValueError("Wrong structure of applications block")

    def parse(self):
        tokens = yaml.scan(self.document)

        for token in tokens:
            token_start = (token.start_mark.line, token.start_mark.column)
            token_end = (token.end_mark.line, token.end_mark.column)

            if isinstance(token, yaml.StreamStartToken):
                self._tree.start = token_start
            if isinstance(token, yaml.StreamEndToken):
                self._tree.end = token_end

            if isinstance(token, ScalarToken) and token.value in ["applications", "services"]:
                resources = ResourcesContainerNode(start=token_start, parent=self._tree)
                
                try:
                    # first we need to skip ValueToken
                    next(tokens)
                    self._process_resources(tokens, resources, resources_name=token.value)
                except ValueError:
                    print("error during apps processing")
                    pass
                if token.value == "applications":
                    self._tree.apps_node = resources
                else:
                    self._tree.services_node = resources

            if isinstance(token, ScalarToken) and token.value == "artifacts":
                try:
                    next(tokens)
                    self._process_artifacts(tokens)
                except ValueError as e:
                    print(f"error during artifacts processing: {e}")
                    pass

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
