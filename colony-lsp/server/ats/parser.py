from typing import Tuple
import yaml
from yaml.tokens import (BlockEndToken, BlockEntryToken, BlockMappingStartToken,
                         BlockSequenceStartToken, KeyToken,
                         ScalarToken, Token, ValueToken, StreamStartToken, StreamEndToken)

from server.ats.trees.app import AppTree
from server.ats.trees.blueprint import BlueprintTree
from server.ats.trees.common import (YamlNode, TextNode, MappingNode, BaseTree,
                                     SequenceNode, NodeError, ObjectNode)
from server.ats.trees.service import ServiceTree


class ParserError(Exception):

    def __init__(self, message: str = None, start_pos: tuple = None, end_pos: tuple = None, token: Token = None):
        self.message = message
        if token is not None:
            self.start_pos = Parser.get_token_start(token)
            self.end_pos = Parser.get_token_end(token)

        else:
            self.start_pos = start_pos
            self.end_pos = end_pos

    def __str__(self) -> str:
        return f"Parser issue with message '{self.message}' on position {self.start_pos} - {self.end_pos}"


class UnprocessedNode(YamlNode):
    def add(self):
        return UnprocessedNode()


class Parser:
    def __init__(self, document: str):
        self.document = self._remove_invalid_characters(document)
        try:
            self.tree = self._get_tree()
        except ValueError as ve:
            raise ParserError(str(ve))

        self.nodes_stack: [YamlNode] = []
        self.tokens_stack: [Token] = []

        self.is_array_item: bool = False

    def _remove_invalid_characters(self, document: str):
        return document.replace('\t', '  ')

    @staticmethod
    def get_token_start(token: Token) -> Tuple[int, int]:
        return token.start_mark.line, token.start_mark.column

    @staticmethod
    def get_token_end(token: Token) -> Tuple[int, int]:
        return token.end_mark.line, token.end_mark.column

    def _handle_hanging_dash(self, token):
        # remove unnecessary empty element added to sequence
        self.nodes_stack.pop()
        
        seq: SequenceNode = self.nodes_stack[-1]
        if not isinstance(seq, SequenceNode):
            raise ParserError(message="Wrong structure of sequence", token=token)

        seq.nodes.pop()
        seq.add_error(NodeError(
            start_pos=self.get_token_start(token),
            end_pos=self.get_token_end(token),
            message="Element could not be empty")
        )

        self.is_array_item = False

    def _process_scalar_token(self, token: ScalarToken):
        node = self.nodes_stack.pop()

        node.start_pos = self.get_token_start(token)
        node.end_pos = self.get_token_end(token)

        if isinstance(node, UnprocessedNode):
            return

        elif isinstance(node, TextNode):
            node.text = token.value

        else:
            # TODO: replace with parser exception
            raise Exception("Wrong node. Expected TextNode")

    def _process_object_child(self, token: ScalarToken):
        """Gets the property of the last Node in a stack and puts
        it to the stack (where property name equals scalar token's value)"""
        self.tokens_stack.pop()
        node: ObjectNode = self.nodes_stack[-1]

        try:
            child_node = node.get_child(token.value)
            child_node.start_pos = self.get_token_start(token)
            self.nodes_stack.append(child_node)
        # TODO: replace with parser exception
        except Exception:
            node.add_error(NodeError(
                start_pos=Parser.get_token_start(token),
                end_pos=Parser.get_token_end(token),
                message=f"Parent node doesn't have child with name '{token.value}'"
            ))
            self.nodes_stack.append(UnprocessedNode())

    def _process_token(self, token: Token) -> None:
        # beginning of document
        if isinstance(token, StreamStartToken):
            self.tree.start_pos = self.get_token_start(token)
            self.tokens_stack.append(token)
            return

        if isinstance(token, BlockEntryToken):
            # Check if before we didn't have empty array element
            if isinstance(self.tokens_stack[-1], BlockEntryToken):
                extra_token = self.tokens_stack.pop()
                self._handle_hanging_dash(extra_token)

            self.tokens_stack.append(token)

            self.is_array_item = True
            # last node in stack must implement add() method
            try:
                node = self.nodes_stack[-1].add()
                self.nodes_stack.append(node)
            except Exception as e:
                raise Exception(f"Unable to add item to the node's container : {e}")

        if isinstance(token, StreamEndToken):
            self.tree.end_pos = self.get_token_start(token)
            return

        # the beginning of the object or mapping
        if isinstance(token, BlockMappingStartToken):
            last_node = self.nodes_stack[-1]
            if (self.is_array_item and isinstance(last_node, MappingNode)
                    and not isinstance(self.tokens_stack[-1], BlockEntryToken)):
                self.tokens_stack.append(token)
                value_node = last_node.get_value()
                self.nodes_stack.append(value_node)
                value_node.start_pos = self.get_token_start(token)
                self.is_array_item = False
                return
            self.tokens_stack.append(token)
            last_node.start_pos = self.get_token_start(token)

        if isinstance(token, BlockSequenceStartToken):
            self.tokens_stack.append(token)
            return

        if isinstance(token, BlockEndToken):
            top = self.tokens_stack.pop()

            # Handle sequence with last empty element
            if isinstance(top, BlockEntryToken):
                self._handle_hanging_dash(top)
                top = self.tokens_stack.pop()

            # TODO: refactor condition
            if (isinstance(top, (BlockMappingStartToken, BlockSequenceStartToken))
                    and isinstance(self.tokens_stack[-1], (ValueToken, BlockEntryToken, StreamStartToken))):
                node = self.nodes_stack.pop()
                node.end_pos = self.get_token_end(token)
                self.tokens_stack.pop()

                return

            elif isinstance(top, ValueToken):
                if self.is_array_item:
                    # case when mapping didn't have value after ':'
                    # inputs:
                    #   API_PORT: 9090
                    #   PORT:

                    # remove last Node and ValueToken and BlockEndToken as well
                    node = self.nodes_stack.pop()
                    node.end_pos = self.get_token_end(token)
                    if not isinstance(self.tokens_stack[-1], (BlockMappingStartToken, BlockSequenceStartToken)):
                        raise Exception("Wrong structure of document")  # TODO: provide better message
                    self.tokens_stack.pop()

                    if not isinstance(self.tokens_stack[-1], BlockEntryToken):
                        raise Exception("Wrong structure of document")  # TODO: provide better message
                    self.tokens_stack.pop()
                    self.is_array_item = False

                    return

                elif isinstance(self.nodes_stack[-1], SequenceNode):
                    # In means that we just finished processing a sequence without indentation
                    # which means document didn't have BlockSequenceStartToken at the beginning of the block
                    # So, this BlockEndToken is related to previous object => we need to remove not only the
                    # List node but also the previous one

                    # first remove sequence node from stack
                    seq_node = self.nodes_stack.pop()
                    # in this case it's ok the end pos will be the same for both objects
                    seq_node.end_pos = self.get_token_end(token)

                    # then check if after ValueToken removal we have any start token on the top of the tokens stack
                    if not isinstance(self.tokens_stack[-1], (BlockMappingStartToken, BlockSequenceStartToken)):
                        raise Exception("Wrong structure of document")  # TODO: provide better message

                    # and remove it from the token stack
                    self.tokens_stack.pop()
                    # and node itself as well
                    prev_node = self.nodes_stack.pop()
                    prev_node.end_pos = self.get_token_end(token)

                    if isinstance(self.tokens_stack[-1], ValueToken):
                        # remove value token opening it
                        self.tokens_stack.pop()
                    return

                else:
                    # We expected a value for property inside object but it wasn't found after ValueToken
                    # It means BlockEndToken closes the parent
                    # Close expected node
                    node = self.nodes_stack.pop()
                    node.end_pos = self.get_token_end(token)
                    # Close parent node
                    self.nodes_stack[-1].end_pos = self.get_token_end(token)
                    self.nodes_stack.pop()

        if isinstance(token, KeyToken):
            # if sequence doesnt have indentation => there is no BlockEndToken at the end
            # and in such case KeyToken will go just after the ValueToken opening the sequence
            # It will also covers issues when object has empty property
            if isinstance(self.tokens_stack[-1], ValueToken):
                # in this case we need first correctly finalize sequence node
                node = self.nodes_stack.pop()
                node.end_pos = self.get_token_start(token)
                self.tokens_stack.pop()  # remove ValueToken

            self.tokens_stack.append(token)
            return

        if isinstance(token, ValueToken):
            self.tokens_stack.append(token)
            return

        if isinstance(token, ScalarToken) and isinstance(self.tokens_stack[-1], ValueToken):
            if self.is_array_item:
                # it means on the top of the stack we must always have MappingNode or it inheritors
                node = self.nodes_stack[-1]

                if not isinstance(node, MappingNode):
                    raise Exception(f"Expected MappingNode, got {type(node)}")

                value_node = node.get_value(expected_type=TextNode)
                self.nodes_stack.append(value_node)

                self.is_array_item = False

            self._process_scalar_token(token)
            self.tokens_stack.pop()
            return

        if isinstance(token, ScalarToken) and isinstance(self.tokens_stack[-1], (KeyToken, BlockEntryToken)):
            if not self.is_array_item:
                self._process_object_child(token)

            else:
                node = self.nodes_stack[-1]

                if isinstance(node, UnprocessedNode) and isinstance(self.tokens_stack[-1], BlockEntryToken):
                    self.nodes_stack.pop()
                    self.is_array_item = False
                    self.tokens_stack.pop()
                    return

                # process object first
                if not isinstance(node, (MappingNode, TextNode)):
                    self.is_array_item = False
                    self._process_object_child(token)
                    return

                if isinstance(node, MappingNode):
                    key_node = node.get_key()
                    self.nodes_stack.append(key_node)

                if isinstance(self.tokens_stack[-1], BlockEntryToken):
                    # case when element in sequence doesn't have value and colon:
                    # inputs:
                    #   - A
                    #   - B
                    last_node = self.nodes_stack[-1]  # store TextNode before deleting
                    self._process_scalar_token(token)

                    self.nodes_stack[-1].end_pos = last_node.end_pos
                    self.nodes_stack[-1].start_pos = last_node.start_pos

                    if isinstance(node, MappingNode):
                        # Sequence was processed as a list of Mapping Nodes
                        self.nodes_stack.pop()

                    self.is_array_item = False

                else:
                    self._process_scalar_token(token)

                self.tokens_stack.pop()

    def parse(self) -> BaseTree:
        data = yaml.scan(self.document, Loader=yaml.FullLoader)
        self.nodes_stack.append(self.tree)

        for token in data:
            self._process_token(token)

        return self.tree

    def _get_tree(self) -> BaseTree:
        trees = {
            'application': AppTree,
            'blueprint': BlueprintTree,
            'TerraForm': ServiceTree
        }

        yaml_obj = yaml.load(self.document, Loader=yaml.FullLoader)
        doc_type = yaml_obj.get('kind', '')

        if doc_type not in trees:
            raise ValueError(f"Unable to initialize tree from document kind '{doc_type}'")

        return trees[doc_type]()
