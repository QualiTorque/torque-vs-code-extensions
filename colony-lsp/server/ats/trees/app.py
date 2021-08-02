from yaml import StreamStartToken, ScalarToken, BlockMappingStartToken, KeyToken, ValueToken, BlockEndToken, \
    StreamEndToken, BlockSequenceStartToken, BlockEntryToken
from dataclasses import dataclass

from server.ats.trees.blueprint import BlueprintTree
from server.ats.trees.common import *


@dataclass
class ConfigurationNode(YamlNode):
    @dataclass
    class InitializationNode(YamlNode):
        script: TextNode = None

    @dataclass
    class StartNode(InitializationNode):
        command: TextNode = None

    @dataclass
    class HealthcheckNode(InitializationNode):
        timeout: TextNode = None
        wait_for_ports: TextNode = None

    initialization: InitializationNode = None
    start: StartNode = None
    healthcheck: HealthcheckNode = None

# IMAGES:


@dataclass
class AmiImageNode(YamlNode):
    id: TextNode = None
    region: TextNode = None
    username: TextNode = None


@dataclass
class AmiSequenceNode(SequenceNode):
    node_type = AmiImageNode


@dataclass
class SourceNode(YamlNode):

    @dataclass
    class ImageNode(YamlNode):
        ami: AmiSequenceNode = None

    image: ImageNode = None


@dataclass
class AppTree(TreeWithOutputs, BaseTree):
    configuration: ConfigurationNode = None
    source: SourceNode = None


import yaml

app_path = "/Users/ddovbii/colony-demo-space-my/applications/My-eCommerce-App-ui/My-eCommerce-App-ui.yaml"

node_stack: [YamlNode] = []
token_stack = []
skip_token: bool = False
is_array_item = False
is_array_processing = False


def _process_scalar_token(token):
    node = node_stack.pop()
    if not isinstance(node, TextNode):
        raise Exception("Wrong node. Expected TextNode")

    node.text = token.value
    node.start_pos = (token.start_mark.line, token.start_mark.column)
    node.end_pos = (token.end_mark.line, token.end_mark.column)


def _process_object_child(token):
    token_stack.pop()
    print(token.value)
    node = node_stack[-1]
    try:
        child_node = node.get_child(token.value)
        child_node.start_pos = (token.start_mark.line, token.start_mark.column)
        node_stack.append(child_node)
    except Exception as e:
        print(f"error during getting a child : {e}")


def process_token(token):
    global is_array_item
    global is_array_processing
    print(f"Processing token : ", token, token.start_mark.line,
          token.start_mark.column, ";", token.end_mark.line, token.end_mark.column)

    # beginning of document
    if isinstance(token, StreamStartToken):
        token_stack.append(token)

    if isinstance(token, BlockEntryToken):
        print("Array Item processing...")
        token_stack.append(token)

        is_array_item = True
        # last node in stack must implement add() method
        try:
            node = node_stack[-1].add()
            node_stack.append(node)
        except Exception as e:
            raise Exception(f"Unable to add item to the node's container : {e}")

    if isinstance(token, StreamEndToken):
        pass
        # TODO: should we consider the end of the tree the last end block or stream end block?
        # node_stack[0].end_pos = (token.end_mark.line, token.end_mark.column)

    # the beginning of the object or mapping
    if isinstance(token, BlockMappingStartToken):
        print("Object started")
        last_node = node_stack[-1]
        if (is_array_item and isinstance(last_node, MappingNode)
                and not isinstance(token_stack[-1], BlockEntryToken)):
            token_stack.append(token)
            value_node = last_node.get_value()
            node_stack.append(value_node)
            value_node.start_pos = (token.start_mark.line, token.start_mark.column)
            is_array_item = False
            return
        token_stack.append(token)
        last_node.start_pos = (token.start_mark.line, token.start_mark.column)

    if isinstance(token, BlockSequenceStartToken):
        is_array_processing = True
        token_stack.append(token)

    if isinstance(token, BlockEndToken):
        top = token_stack.pop()
        # TODO: refactor condition
        if (isinstance(top, (BlockMappingStartToken, BlockSequenceStartToken))
                and isinstance(token_stack[-1], (ValueToken, BlockEntryToken, StreamStartToken))):
            node = node_stack.pop()
            node.end_pos = (token.end_mark.line, token.end_mark.column)
            token_stack.pop()

            if isinstance(top, BlockSequenceStartToken):
                is_array_processing = False

            return

        if isinstance(top, ValueToken) and is_array_item:
            # case when mapping didn't have value after ':'
            # inputs:
            #   API_PORT: 9090
            #   PORT:

            # remove last Node and ValueToken and BlockEndToken as well
            node = node_stack.pop()
            node.end_pos = (token.end_mark.line, token.end_mark.column)
            if not isinstance(token_stack[-1], (BlockMappingStartToken, BlockSequenceStartToken)):
                raise Exception("Wrong structure of document")  # TODO: provide better message
            token_stack.pop()

            if not isinstance(token_stack[-1], BlockEntryToken):
                raise Exception("Wrong structure of document")  # TODO: provide better message
            token_stack.pop()
            is_array_item = False

            return

        if isinstance(top, ValueToken) and isinstance(node_stack[-1], SequenceNode):
            # In means that we just finished processing a sequence without indentation
            # which means document didn't have BlockSequenceStartToken at the beginning of the block
            # So, this BlockEndToken is related to previous object => we need to remove not only the List node but also
            # the previous one

            # first remove sequence node from stack
            seq_node = node_stack.pop()
            # in this case it's ok the end pos will be the same for both objects
            seq_node.end_pos = (token.end_mark.line, token.end_mark.column)

            # then check if after ValueToken removal we have any start token on the top of the tokens stack
            if not isinstance(token_stack[-1], (BlockMappingStartToken, BlockSequenceStartToken)):
                raise Exception("Wrong structure of document")  # TODO: provide better message

            # and remove it from the token stack
            token_stack.pop()
            # and node itself as well
            prev_node = node_stack.pop()
            prev_node.end_pos = (token.end_mark.line, token.end_mark.column)

            if isinstance(token_stack[-1], ValueToken):
                # remove value token opening it
                token_stack.pop()

    if isinstance(token, KeyToken):
        # if sequence doesnt have indentation => there is no BlockEndToken at the end
        # and in such case KeyToken will go just after the ValueToken opening the sequence
        if isinstance(token_stack[-1], ValueToken):
            is_array_processing = False
            # in this case we need first correctly finalize sequence node
            node = node_stack.pop()
            node.end_pos = (token.start_mark.line, token.start_mark.column)
            token_stack.pop()  # remove ValueToken

        token_stack.append(token)

    if isinstance(token, ValueToken):
        token_stack.append(token)

    if isinstance(token, ScalarToken) and isinstance(token_stack[-1], ValueToken):
        if is_array_item:
            # it means on the top of the stack we must always have MappingNode or it inheritors
            node = node_stack[-1]

            if not isinstance(node, MappingNode):
                raise Exception(f"Expected MappingNode, got {type(node)}")

            value_node = node.get_value(expected_type=TextNode)
            node_stack.append(value_node)

            is_array_item = False

        _process_scalar_token(token)
        token_stack.pop()

    if isinstance(token, ScalarToken) and isinstance(token_stack[-1], (KeyToken, BlockEntryToken)):
        if not is_array_item:
            _process_object_child(token)

        else:
            node = node_stack[-1]

            # process object first
            if not isinstance(node, (MappingNode, TextNode)):
                is_array_item = False
                _process_object_child(token)
                return

            if isinstance(node, MappingNode):
                key_node = node.get_key()
                node_stack.append(key_node)

            if isinstance(token_stack[-1], BlockEntryToken):
                # case when element in sequence doesn't have value and colon:
                # inputs:
                #   - A
                #   - B
                last_node = node_stack[-1] # store TextNode before deleting
                _process_scalar_token(token)

                node_stack[-1].end_pos = last_node.end_pos
                node_stack[-1].start_pos = last_node.start_pos

                if isinstance(node, MappingNode):
                    # Sequence was processed as a list of Mapping Nodes
                    node_stack.pop()

                is_array_item = False

            else:
                _process_scalar_token(token)

            token_stack.pop()


bp_path = "/Users/ddovbii/colony-demo-space-my/blueprints/promotions-manager-all-aws.yaml"

with open(bp_path, "r") as f:
    data = yaml.scan(f, Loader=yaml.FullLoader)
    bp_tree = BlueprintTree()
    node_stack.append(bp_tree)

    for tok in data:
        process_token(tok)
    print(bp_tree)
