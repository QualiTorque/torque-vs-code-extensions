import yaml
from yaml.tokens import (BlockEndToken, BlockEntryToken, BlockMappingStartToken,
                         BlockSequenceStartToken, KeyToken,
                         ScalarToken, Token, ValueToken, StreamStartToken, StreamEndToken)

from server.ats.trees.app import AppTree
from server.ats.trees.blueprint import *
from server.ats.trees.common import *
from server.ats.trees.service import ServiceTree


class Parser:
    def __init__(self, document: str):
        self.document = document
        try:
            self.tree = self._get_tree()
        except ValueError:
            # TODO: replace with parser exception
            raise NotImplementedError()

        self.nodes_stack: [YamlNode] = []
        self.tokens_stack: [Token] = []

        self.is_array_item: bool = False

    def _process_scalar_token(self, token: ScalarToken):
        node: TextNode = self.nodes_stack.pop()
        if not isinstance(node, TextNode):
            # TODO: replace with parser exception
            raise Exception("Wrong node. Expected TextNode")

        node.text = token.value
        node.start_pos = (token.start_mark.line, token.start_mark.column)
        node.end_pos = (token.end_mark.line, token.end_mark.column)

    def _process_object_child(self, token: ScalarToken):
        """Gets the property of the last Node in a stack and puts
        it to the stack (where property name equals scalar token's value)"""
        self.tokens_stack.pop()
        node = self.nodes_stack[-1]
        try:
            child_node = node.get_child(token.value)
            child_node.start_pos = (token.start_mark.line, token.start_mark.column)
            self.nodes_stack.append(child_node)
        # TODO: replace with parser exception
        except Exception as e:
            print(f"error during getting a child : {e}")

    def _process_token(self, token: Token) -> None:

        print(f"Processin token: {token}")
        # beginning of document
        if isinstance(token, StreamStartToken):
            self.tree.start_pos = (token.start_mark.line, token.start_mark.column)
            self.tokens_stack.append(token)
            return

        if isinstance(token, BlockEntryToken):
            self.tokens_stack.append(token)

            self.is_array_item = True
            # last node in stack must implement add() method
            try:
                node = self.nodes_stack[-1].add()
                self.nodes_stack.append(node)
            except Exception as e:
                raise Exception(f"Unable to add item to the node's container : {e}")

        if isinstance(token, StreamEndToken):
            self.tree.end_pos = (token.start_mark.line, token.start_mark.column)
            return

        # the beginning of the object or mapping
        if isinstance(token, BlockMappingStartToken):
            last_node = self.nodes_stack[-1]
            if (self.is_array_item and isinstance(last_node, MappingNode)
                    and not isinstance(self.tokens_stack[-1], BlockEntryToken)):
                self.tokens_stack.append(token)
                value_node = last_node.get_value()
                self.nodes_stack.append(value_node)
                value_node.start_pos = (token.start_mark.line, token.start_mark.column)
                self.is_array_item = False
                return
            self.tokens_stack.append(token)
            last_node.start_pos = (token.start_mark.line, token.start_mark.column)

        if isinstance(token, BlockSequenceStartToken):
            self.tokens_stack.append(token)
            return

        if isinstance(token, BlockEndToken):
            top = self.tokens_stack.pop()
            # TODO: refactor condition
            if (isinstance(top, (BlockMappingStartToken, BlockSequenceStartToken))
                    and isinstance(self.tokens_stack[-1], (ValueToken, BlockEntryToken, StreamStartToken))):
                node = self.nodes_stack.pop()
                node.end_pos = (token.end_mark.line, token.end_mark.column)
                self.tokens_stack.pop()

                return

            if isinstance(top, ValueToken) and self.is_array_item:
                # case when mapping didn't have value after ':'
                # inputs:
                #   API_PORT: 9090
                #   PORT:

                # remove last Node and ValueToken and BlockEndToken as well
                node = self.nodes_stack.pop()
                node.end_pos = (token.end_mark.line, token.end_mark.column)
                if not isinstance(self.tokens_stack[-1], (BlockMappingStartToken, BlockSequenceStartToken)):
                    raise Exception("Wrong structure of document")  # TODO: provide better message
                self.tokens_stack.pop()

                if not isinstance(self.tokens_stack[-1], BlockEntryToken):
                    raise Exception("Wrong structure of document")  # TODO: provide better message
                self.tokens_stack.pop()
                self.is_array_item = False

                return

            if isinstance(top, ValueToken) and isinstance(self.nodes_stack[-1], SequenceNode):
                # In means that we just finished processing a sequence without indentation
                # which means document didn't have BlockSequenceStartToken at the beginning of the block
                # So, this BlockEndToken is related to previous object => we need to remove not only the
                # List node but also the previous one

                # first remove sequence node from stack
                seq_node = self.nodes_stack.pop()
                # in this case it's ok the end pos will be the same for both objects
                seq_node.end_pos = (token.end_mark.line, token.end_mark.column)

                # then check if after ValueToken removal we have any start token on the top of the tokens stack
                if not isinstance(self.tokens_stack[-1], (BlockMappingStartToken, BlockSequenceStartToken)):
                    raise Exception("Wrong structure of document")  # TODO: provide better message

                # and remove it from the token stack
                self.tokens_stack.pop()
                # and node itself as well
                prev_node = self.nodes_stack.pop()
                prev_node.end_pos = (token.end_mark.line, token.end_mark.column)

                if isinstance(self.tokens_stack[-1], ValueToken):
                    # remove value token opening it
                    self.tokens_stack.pop()
                return

        if isinstance(token, KeyToken):
            # if sequence doesnt have indentation => there is no BlockEndToken at the end
            # and in such case KeyToken will go just after the ValueToken opening the sequence
            if isinstance(self.tokens_stack[-1], ValueToken):
                # in this case we need first correctly finalize sequence node
                node = self.nodes_stack.pop()
                node.end_pos = (token.start_mark.line, token.start_mark.column)
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

                value_node = node.get_value()
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

    def parse(self) -> None:
        data = yaml.scan(self.document, Loader=yaml.FullLoader)
        self.nodes_stack.append(self.tree)

        for token in data:
            self._process_token(token)

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

bp_path = "/Users/ddovbii/colony-demo-space-my/blueprints/My-eCommerce-App.yaml"
with open(bp_path, 'r') as f:
    doc = f.read()

    parser = Parser(doc)
    parser.parse()
    tree = parser.tree
    print(tree)