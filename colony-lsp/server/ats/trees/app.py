from yaml import StreamStartToken, ScalarToken, BlockMappingStartToken, KeyToken, ValueToken, BlockEndToken, \
    StreamEndToken
from dataclasses import dataclass
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


@dataclass
class AppTree(BaseTree, TreeWithOutputs):
    configuration: ConfigurationNode = None
    pass

import yaml

app_path = "/Users/ddovbii/colony-demo-space-my/applications/My-eCommerce-App-ui/My-eCommerce-App-ui.yaml"

node_stack: [YamlNode] = []
token_stack = []
skip_token: bool = False


def process_token(token):
    print(f"Processing token : {token}")

    # beginning of document
    if isinstance(token, StreamStartToken):
        token_stack.append(token)
        node_stack.append(AppTree())

    if isinstance(token, StreamEndToken):
        node_stack[0].end_pos = (token.end_mark.line, token.end_mark.column)

    # the beginning of the object
    if isinstance(token, BlockMappingStartToken):
        node_stack[-1].start_pos = (token.start_mark.line, token.start_mark.column)
        token_stack.append(token)

    if isinstance(token, BlockEndToken):
        top = token_stack.pop()

        if isinstance(top, BlockMappingStartToken) and isinstance(token_stack[-1], ValueToken):
            node_stack.pop()
            token_stack.pop()

    if isinstance(token, KeyToken) or isinstance(token, ValueToken):
        token_stack.append(token)
        return

    if isinstance(token, ScalarToken) and isinstance(token_stack[-1], ValueToken):
        node = node_stack.pop()
        if not isinstance(node, TextNode):
            raise Exception("Wrong node. Expected TextNode")

        node.text = token.value
        node.start_pos = (token.start_mark.line, token.start_mark.column)
        node.end_pos = (token.end_mark.line, token.end_mark.column)

        token_stack.pop()

    if isinstance(token, ScalarToken) and isinstance(token_stack[-1], KeyToken):
        token_stack.pop()
        print(token.value)
        node = node_stack[-1]
        try:
            child_node = node.get_child(token.value)
            node_stack.append(child_node)
        except Exception as e:
            print(f"error during getting a child : {e}")


with open(app_path, "r") as f:
    data = yaml.scan(f, Loader=yaml.FullLoader)
    for tok in data:
        process_token(tok)
    print(node_stack)
