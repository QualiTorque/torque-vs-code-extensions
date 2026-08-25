import re
from typing import List, Tuple

import yaml
from server.ats.trees.app import AppTree
from server.ats.trees.blueprint import BlueprintTree
from server.ats.trees.blueprint_v2 import BlueprintV2Tree, FreeFormNode
from server.ats.trees.common import (
    BaseTree,
    MapNode,
    MappingNode,
    NodeError,
    ObjectNode,
    PropertyNode,
    SequenceNode,
    TextNode,
    YamlNode,
)
from server.ats.trees.service import ServiceTree
from yaml.tokens import (
    BlockEndToken,
    BlockEntryToken,
    BlockMappingStartToken,
    BlockSequenceStartToken,
    FlowEntryToken,
    FlowMappingEndToken,
    FlowMappingStartToken,
    FlowSequenceEndToken,
    FlowSequenceStartToken,
    KeyToken,
    ScalarToken,
    StreamEndToken,
    StreamStartToken,
    Token,
    ValueToken,
)

# Codepoint ranges pyyaml's Reader is willing to read. Anything outside them
# makes it raise ReaderError before scanning even starts - typically mojibake,
# a C1 control byte produced by a double encoded em-dash. The server's
# YamlDotNet accepts such a document, so it must be parsed here as well instead
# of losing every diagnostic in the file.
# Same ranges as yaml.reader.Reader.NON_PRINTABLE; the pattern is built from
# codepoints so that this source file stays plain ASCII.
PRINTABLE_RANGES = [
    (0x09, 0x09),
    (0x0A, 0x0A),
    (0x0D, 0x0D),
    (0x20, 0x7E),
    (0x85, 0x85),
    (0xA0, 0xD7FF),
    (0xE000, 0xFFFD),
    (0x10000, 0x10FFFF),
]
NON_PRINTABLE_REGEX = re.compile(
    "[^"
    + "".join(chr(low) + "-" + chr(high) for low, high in PRINTABLE_RANGES)
    + "]"
)


def replace_unprintable_characters(document: str) -> str:
    """Makes a document readable by pyyaml without moving anything in it.

    Every character is replaced by exactly one space, so all the positions
    reported afterwards still match the document the client holds."""
    return NON_PRINTABLE_REGEX.sub(" ", document)


class ParserError(Exception):
    def __init__(
        self,
        message: str = None,
        start_pos: tuple = None,
        end_pos: tuple = None,
        token: Token = None,
    ):
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


# A block sequence written at the same indentation as its key produces no
# BlockSequenceStartToken, so the token closing it belongs to the parent and
# the parser has to unwind one level more than usual. These are the nodes that
# may be found holding such a sequence: a real SequenceNode, the placeholder
# used for content the tree does not model, and a free form section (which
# represents both mappings and sequences with the very same node type).
SEQUENCE_LIKE_NODES = (UnprocessedNode, SequenceNode, FreeFormNode)


class Parser:
    def __init__(self, document: str):
        self.document = self._remove_invalid_characters(document)
        try:
            self.tree = self._get_tree()
        except ValueError as ve:
            raise ParserError(str(ve), (0,0), (0,0))

        self.nodes_stack: List[YamlNode] = []
        self.tokens_stack: List[Token] = []

        self.is_array_item: bool = False
        self.processing_map_element: bool = False

    def _remove_invalid_characters(self, document: str):
        return replace_unprintable_characters(document.replace("\t", "  "))

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
        seq.add_error(
            NodeError(
                start_pos=self.get_token_start(token),
                end_pos=self.get_token_end(token),
                message="Element could not be empty",
            )
        )

        self.is_array_item = False

    def _process_scalar_token(self, token: ScalarToken):
        node = self.nodes_stack.pop()

        node.start_pos = self.get_token_start(token)
        node.end_pos = self.get_token_end(token)

        if isinstance(node, TextNode):                
            node.text = token.value
            node.style = token.style

        else:
            # TODO: replace with parser exception
            raise Exception("Wrong node. Expected TextNode")

    def _process_map_element(self, token: ScalarToken):
        pass

    def _process_object_child(self, token: ScalarToken):
        """Gets the property of the last Node in a stack and puts
        it to the stack (where property name equals scalar token's value)"""
        _ = self.tokens_stack.pop()
        node: ObjectNode = self.nodes_stack[-1]

        try:
            child_node = node.get_child(token.value)
            child_node.start_pos = self.get_token_start(token)

        # TODO: replace with parser exception
        except AttributeError:
            node.add_error(
                NodeError(
                    start_pos=Parser.get_token_start(token),
                    end_pos=Parser.get_token_end(token),
                    message=f"Parent node does not have child with name '{token.value}'",
                )
            )
            self.nodes_stack.append(UnprocessedNode())
            return

        if not isinstance(child_node, MappingNode):
            raise ParserError(message="Parsing error. Expected mapping", token=token)

        child_node.key.start_pos = self.get_token_start(token)
        child_node.key.end_pos = self.get_token_end(token)
        self.nodes_stack.append(child_node)

    def _process_token(self, token: Token) -> None:
        if (
            self.nodes_stack
            and isinstance(self.nodes_stack[-1], PropertyNode)
            and isinstance(token, (KeyToken, BlockEndToken))
        ):

            self.nodes_stack[-1].end_pos = self.get_token_end(token)
            self.nodes_stack.pop()

            # case with empty value:
            if isinstance(self.tokens_stack[-1], ValueToken):
                self.tokens_stack.pop()

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

            if isinstance(self.nodes_stack[-1], MappingNode):
                # We are processing the first element of array but sequence wasn't created yet
                val: YamlNode = self.nodes_stack[-1].get_value()
                val.start_pos = self.get_token_start(token)
                self.nodes_stack.append(val)

            self.tokens_stack.append(token)

            self.is_array_item = True
            # last node in stack must implement add() method
            try:
                node = self.nodes_stack[-1].add()
                self.nodes_stack.append(node)

                if isinstance(node, ObjectNode):
                    node.start_pos = self.get_token_end(token)

            except Exception:
                raise ParserError("Wrong structure of document", token=token)
                # raise Exception(f"Unable to add item to the node's container : {e}")

        if isinstance(token, StreamEndToken):
            self.tree.end_pos = self.get_token_start(token)
            # since there could be unclosed nodes due to errors
            # we need to set end_pos for them as well
            while self.nodes_stack:
                node: YamlNode = self.nodes_stack.pop()
                node.end_pos = self.get_token_start(token)
            return

        # the beginning of the object or mapping
        if isinstance(token, BlockMappingStartToken):
            last_node = self.nodes_stack[-1]

            if isinstance(last_node, MappingNode) and not isinstance(
                self.tokens_stack[-1], BlockEntryToken
            ):
                self.tokens_stack.append(token)
                value_node = last_node.get_value()
                self.nodes_stack.append(value_node)
                value_node.start_pos = self.get_token_start(token)

                if self.is_array_item:
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
            if isinstance(
                top, (BlockMappingStartToken, BlockSequenceStartToken)
            ) and isinstance(
                self.tokens_stack[-1], (ValueToken, BlockEntryToken, StreamStartToken)
            ):
                node = self.nodes_stack.pop()
                end_pos = self.get_token_end(token)
                node.end_pos = end_pos
                
                if len(self.nodes_stack) > 1 and isinstance(self.nodes_stack[-2], MapNode):
                    self.nodes_stack[-1].end_pos = end_pos
                    self.nodes_stack.pop()
                    self.processing_map_element = False

                self.tokens_stack.pop()

            elif isinstance(top, ValueToken):
                if self.is_array_item:
                    # case when mapping didn't have value after ':'
                    # inputs:
                    #   API_PORT: 9090
                    #   PORT:

                    # remove last Node and ValueToken and BlockEndToken as well
                    node = self.nodes_stack.pop()
                    node.end_pos = self.get_token_end(token)
                    if not isinstance(
                        self.tokens_stack[-1],
                        (BlockMappingStartToken, BlockSequenceStartToken),
                    ):
                        raise Exception(
                            "Wrong structure of document"
                        )  # TODO: provide better message
                    self.tokens_stack.pop()

                    if not isinstance(self.tokens_stack[-1], BlockEntryToken):
                        raise Exception(
                            "Wrong structure of document"
                        )  # TODO: provide better message
                    self.tokens_stack.pop()
                    self.is_array_item = False

                elif isinstance(self.nodes_stack[-1], SEQUENCE_LIKE_NODES):
                    # In means that we just finished processing a sequence without indentation
                    # which means document didn't have BlockSequenceStartToken at the beginning of the block
                    # So, this BlockEndToken is related to previous object => we need to remove not only the
                    # List node but also the previous one

                    # first remove sequence node from stack
                    seq_node = self.nodes_stack.pop()
                    # in this case it's ok the end pos will be the same for both objects
                    seq_node.end_pos = self.get_token_end(token)

                    # check if we have property on top
                    if isinstance(self.nodes_stack[-1], PropertyNode):
                        self.nodes_stack[-1].end_pos = self.get_token_end(token)
                        self.nodes_stack.pop()

                    # then check if after ValueToken removal we have any start token on the top of the tokens stack
                    if not isinstance(
                        self.tokens_stack[-1],
                        (BlockMappingStartToken, BlockSequenceStartToken),
                    ):
                        raise Exception(
                            "Wrong structure of document"
                        )  # TODO: provide better message

                    # and remove it from the token stack
                    self.tokens_stack.pop()
                    # and node itself as well
                    prev_node = self.nodes_stack.pop()
                    prev_node.end_pos = self.get_token_end(token)

                    # The object just closed may be the value of a map element
                    # ('My Input:' under 'inputs:'), and then the element is
                    # over as well - the same unwinding the indented form gets
                    # from its own BlockEndToken. Without it the next key of
                    # the map would be written over the current element.
                    if len(self.nodes_stack) > 1 and isinstance(
                        self.nodes_stack[-2], MapNode
                    ):
                        self.nodes_stack[-1].end_pos = self.get_token_end(token)
                        self.nodes_stack.pop()
                        self.processing_map_element = False

                    if isinstance(self.tokens_stack[-1], (ValueToken, BlockEntryToken)):
                        # remove value token opening it
                        self.tokens_stack.pop()

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
            # It also covers issues when object has empty property
            if isinstance(self.tokens_stack[-1], ValueToken):
                # in this case we need first correctly finalize sequence node
                node = self.nodes_stack.pop()
                node.end_pos = self.get_token_start(token)
                self.tokens_stack.pop()  # remove ValueToken

                # and also handle property if exist
                if isinstance(self.nodes_stack[-1], PropertyNode):
                    prop = self.nodes_stack.pop()
                    prop.end_pos = self.get_token_end(token)

            # Case when key followed after sequence with no indentation
            # and the last element of this sequence was empty
            if self.is_array_item and isinstance(
                self.tokens_stack[-1], BlockEntryToken
            ):
                self._handle_hanging_dash(self.tokens_stack[-1])
                self.tokens_stack.pop()  # remove BlockEntryToken
                node = self.nodes_stack.pop()  # remove sequence
                node.end_pos = self.get_token_end(token)

                if isinstance(self.tokens_stack[-1], ValueToken):
                    self.tokens_stack.pop()

                # and also handle property if exist
                if isinstance(self.nodes_stack[-1], PropertyNode):
                    prop = self.nodes_stack.pop()
                    prop.end_pos = self.get_token_end(token)

            if isinstance(self.nodes_stack[-1], MapNode):
                mapping = self.nodes_stack[-1].add()
                self.nodes_stack.append(mapping)
                mapping.start_pos = self.get_token_start(token)
                self.processing_map_element = True

            self.tokens_stack.append(token)
            return

        if isinstance(token, ValueToken):
            self.tokens_stack.append(token)
            return

        if isinstance(token, ScalarToken) and isinstance(
            self.tokens_stack[-1], ValueToken
        ):
            node = self.nodes_stack[-1]
            if isinstance(node, UnprocessedNode):
                self.nodes_stack.pop()
                self.tokens_stack.pop()
                return

            if not isinstance(node, MappingNode):
                raise ParserError(message="Expected mapping value here", token=token)
            try:
                value_node = node.get_value(expected_type=TextNode)
            except ValueError:
                raise ParserError(
                    message="Scalar cannot be accepted here. Object expected",
                    token=token,
                )
            self.nodes_stack.append(value_node)

            self._process_scalar_token(token)
            self.tokens_stack.pop()

            if self.is_array_item:
                self.is_array_item = False
            return

        if isinstance(token, ScalarToken) and isinstance(
            self.tokens_stack[-1], (KeyToken, BlockEntryToken)
        ):
            node = self.nodes_stack[-1]

            if not self.is_array_item:
                if isinstance(node, MappingNode):
                    key_node = node.get_key()
                    self.nodes_stack.append(key_node)
                    self._process_scalar_token(token)
                    self.tokens_stack.pop()
                else:
                    self._process_object_child(token)
                return
            
            else:
                if isinstance(node, UnprocessedNode) and isinstance(
                    self.tokens_stack[-1], BlockEntryToken
                ):
                    self.nodes_stack.pop()
                    self.is_array_item = False
                    self.tokens_stack.pop()
                    return

                # process object first
                if not isinstance(node, (MappingNode, TextNode)) and isinstance(self.tokens_stack[-1], KeyToken):
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
                    last_node: YamlNode = self.nodes_stack[-1]  # store TextNode before deleting
                    if last_node.get_shortened_form_property() is not None:
                        last_node.end_pos = self.get_token_end(token)
                        _ = self.nodes_stack.pop()
                        self.nodes_stack.append(last_node.get_shortened_form_property())


                    self._process_scalar_token(token)

                    self.nodes_stack[-1].end_pos = last_node.end_pos
                    self.nodes_stack[-1].start_pos = last_node.start_pos

                    if isinstance(node, MappingNode):
                        # Sequence was processed as a list of Mapping Nodes
                        _ = self.nodes_stack.pop()

                    self.is_array_item = False

                else:
                    self._process_scalar_token(token)

                self.tokens_stack.pop()

    @staticmethod
    def _rewrite_flow_tokens(tokens: List[Token]) -> List[Token]:
        """Rewrites flow style collections into their block style equivalent.

        Flow style ('allowed-values: [a, b]', 'labels: {x: y}') is ordinary
        YAML and the server accepts it, but the token stream it produces is
        different from the block one this parser is built around. The two
        describe the very same structure though, so translating the tokens is
        enough to support flow style everywhere without touching the parsing
        logic itself:

            [a, b]      ->  BlockSequenceStart Entry a Entry b BlockEnd
            {k: v}      ->  BlockMappingStart Key k Value v BlockEnd

        Block style streams contain none of these tokens and are returned
        unchanged.
        """
        result = []
        # one entry per open flow collection: True for a sequence
        flow_stack: List[bool] = []
        total = len(tokens)
        index = 0

        while index < total:
            token = tokens[index]
            following = tokens[index + 1] if index + 1 < total else None

            if isinstance(token, (FlowSequenceStartToken, FlowMappingStartToken)):
                is_sequence = isinstance(token, FlowSequenceStartToken)
                closing = (
                    FlowSequenceEndToken if is_sequence else FlowMappingEndToken
                )

                # An empty collection has no block equivalent at all: a block
                # sequence or mapping is opened by its first element. Dropping
                # both tokens leaves 'key:' with no value, exactly like the
                # empty block form.
                if isinstance(following, closing):
                    index += 2
                    continue

                start_class = (
                    BlockSequenceStartToken if is_sequence else BlockMappingStartToken
                )
                result.append(start_class(token.start_mark, token.end_mark))
                flow_stack.append(is_sequence)

                if is_sequence and following is not None:
                    result.append(
                        BlockEntryToken(following.start_mark, following.start_mark)
                    )

                index += 1
                continue

            if isinstance(token, FlowEntryToken):
                # A separator between mapping pairs has no block counterpart,
                # and a trailing comma ('[a, b,]') separates nothing at all.
                if (
                    flow_stack
                    and flow_stack[-1]
                    and following is not None
                    and not isinstance(following, FlowSequenceEndToken)
                ):
                    result.append(
                        BlockEntryToken(following.start_mark, following.start_mark)
                    )

                index += 1
                continue

            if isinstance(token, (FlowSequenceEndToken, FlowMappingEndToken)):
                result.append(BlockEndToken(token.start_mark, token.end_mark))

                if flow_stack:
                    flow_stack.pop()

                index += 1
                continue

            result.append(token)
            index += 1

        return result

    def parse(self) -> BaseTree:
        # the stream is materialized because rewriting flow style tokens
        # needs to look at the token following the current one
        data = self._rewrite_flow_tokens(
            list(yaml.scan(self.document, Loader=yaml.FullLoader))
        )

        if self.tree:
            self.nodes_stack.append(self.tree)

            for token in data:
                self._process_token(token)

        return self.tree

    def _get_tree(self) -> BaseTree:
        trees = {
            "application": AppTree,
            "blueprint": BlueprintTree,
            "TerraForm": ServiceTree,
        }

        yaml_obj = yaml.load(self.document, Loader=yaml.FullLoader)
        spec_version = yaml_obj.get("spec_version", None)

        if spec_version == 1:
            doc_type = yaml_obj.get("kind", "")
            if doc_type not in trees:
                raise ValueError(
                    f"Unable to initialize tree from document kind '{doc_type}'"
                )
            return trees[doc_type]()
        elif spec_version in ["2-preview", 2]:
            return BlueprintV2Tree()

        else:
            raise ValueError("Unable to build a tree. Unknown spec_version")
