############################################################################
# Copyright(c) Open Law Library. All rights reserved.                      #
# See ThirdPartyNotices.txt in the project root for additional notices.    #
#                                                                          #
# Licensed under the Apache License, Version 2.0 (the "License")           #
# you may not use this file except in compliance with the License.         #
# You may obtain a copy of the License at                                  #
#                                                                          #
#     http: // www.apache.org/licenses/LICENSE-2.0                         #
#                                                                          #
# Unless required by applicable law or agreed to in writing, software      #
# distributed under the License is distributed on an "AS IS" BASIS,        #
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. #
# See the License for the specific language governing permissions and      #
# limitations under the License.                                           #
############################################################################
import asyncio
import json
import time
import uuid
import os
import glob
import pathlib
from json import JSONDecodeError
from typing import Optional, Tuple

from pygls.lsp.methods import (COMPLETION, COMPLETION_ITEM_RESOLVE, TEXT_DOCUMENT_DID_CHANGE,
                               TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN, HOVER)
from pygls.lsp.types import (CompletionItem, CompletionList, CompletionOptions,
                             CompletionParams, ConfigurationItem,
                             ConfigurationParams, Diagnostic,
                             DidChangeTextDocumentParams, 
                             DidCloseTextDocumentParams, Hover, TextDocumentPositionParams,
                             DidOpenTextDocumentParams, MessageType, Position,
                             Range, Registration, RegistrationParams,
                             Unregistration, UnregistrationParams, workspace)
from pygls.server import LanguageServer
from pygls.workspace import Document, position_from_utf16

COUNT_DOWN_START_IN_SECONDS = 10
COUNT_DOWN_SLEEP_IN_SECONDS = 1


class ColonyLanguageServer(LanguageServer):
    CMD_COUNT_DOWN_BLOCKING = 'countDownBlocking'
    CMD_COUNT_DOWN_NON_BLOCKING = 'countDownNonBlocking'
    CMD_REGISTER_COMPLETIONS = 'registerCompletions'
    CMD_SHOW_CONFIGURATION_ASYNC = 'showConfigurationAsync'
    CMD_SHOW_CONFIGURATION_CALLBACK = 'showConfigurationCallback'
    CMD_SHOW_CONFIGURATION_THREAD = 'showConfigurationThread'
    CMD_UNREGISTER_COMPLETIONS = 'unregisterCompletions'

    CONFIGURATION_SECTION = 'colonyServer'

    def __init__(self):
        super().__init__()


colony_server = ColonyLanguageServer()

def _preceding_words(document: Document, position: Position) -> Optional[Tuple[str, str]]:
    """
    Get the word under the cursor returning the start and end positions.
    """
    lines = document.lines
    if position.line >= len(lines):
        return None

    row, col = position_from_utf16(lines, position)
    line = lines[row]
    try:
        word = line[:col].strip().split()[-2:]
        return word
    except (ValueError):
        return None

def _get_app_scripts(app_dir_path: str):
    scripts = []
    files = pathlib.Path(app_dir_path.replace("file://", "")).parent.glob("./*")
    for file in files:
        if not file.name.endswith('.yaml'):
            scripts.append(pathlib.Path(file).name)

    return scripts


def _validate(ls, params):
    ls.show_message_log('Validating yaml...')

    text_doc = ls.workspace.get_document(params.text_document.uri)

    source = text_doc.source
    diagnostics = _validate_yaml(source) if source else []

    ls.publish_diagnostics(text_doc.uri, diagnostics)


def _validate_yaml(source):
    """Validates yaml file."""
    diagnostics = []

    try:
        yaml.load(source, Loader=yaml.SafeLoader)
    except yaml.MarkedYAMLError as ex:
        mark = ex.problem_mark
        print(mark)
        d = Diagnostic(
            range=Range(
                start=Position(line=mark.line - 1, character=mark.column - 1),
                end=Position(line=mark.line - 1, character=mark.column)
            ),
            message=ex.problem,
            source=type(colony_server).__name__
        )
        print(d)

        diagnostics.append(d)

    return diagnostics


@colony_server.feature(COMPLETION_ITEM_RESOLVE, CompletionOptions())
def completion_item_resolve(server: ColonyLanguageServer, params: CompletionItem) -> CompletionItem:
    """Resolves documentation and detail of given completion item."""
    print('completion_item_resolve')
    print(server)
    print(params)
    print('---------')
    if params.label == 'debugging':
        #completion = _MOST_RECENT_COMPLETIONS[item.label]
        params.detail = "debugging description"
        docstring = "some docstring" #convert_docstring(completion.docstring(), markup_kind)
        params.documentation = "documention"  #MarkupContent(kind=markup_kind, value=docstring)
        return params
    # markup_kind = _choose_markup(server)
    # return jedi_utils.lsp_completion_item_resolve(
    #     params, markup_kind=markup_kind
    # )

@colony_server.feature(COMPLETION, CompletionOptions(resolve_provider=True))
def completions(params: Optional[CompletionParams] = None) -> CompletionList:
    """Returns completion items."""
    doc = colony_server.workspace.get_document(params.text_document.uri)
    fdrs = colony_server.workspace.folders
    root = colony_server.workspace.root_path
    print('completion')
    print(params)
    print('--------')
    if '/blueprints/' in params.text_document.uri:        
        items=[
                CompletionItem(label='applications'),
                CompletionItem(label='clouds'),
                CompletionItem(label='debugging'),
                CompletionItem(label='ingress'),
                CompletionItem(label='availability'),
            ]
        apps_path = ospath.join(str(Path(params.text_document.uri).parents[1]).replace('file:',''), 'applications')
        for dir in os.listdir(apps_path):
            app_dir = ospath.join(apps_path, dir)
            if ospath.isdir(app_dir):
                files = os.listdir(app_dir)
                if f'{dir}.yaml' in files:
                    output = f"  - {dir}:\n"
                    with open(ospath.join(app_dir, f'{dir}.yaml')) as file:
                        app_file = yaml.load(file, Loader=yaml.FullLoader)
                        inputs = app_file['inputs'] if 'inputs' in app_file else None
                        if inputs:
                            output += "      instances: 1\n"
                            output += "      inputs_value:\n"
                            for input in inputs:
                                if isinstance(input, str):
                                    output += f"      - {input}: \n"
                                elif isinstance(input, dict):
                                    for k,v in input.items():
                                        output += f"      - {k}: {v}\n"
                    items.append(CompletionItem(label=dir, kind=CompletionItemKind.Reference, insert_text=output))
        return CompletionList(
            is_incomplete=False,
            items=items
        )
    elif '/applications/' in params.text_document.uri:
        words = _preceding_words(
            colony_server.workspace.get_document(params.text_document.uri),
            params.position)
        # debug("words", words)
        if words[0].startswith("script"):
            scripts = _get_app_scripts(params.text_document.uri)
            return CompletionList(
                is_incomplete=False,
                items=[CompletionItem(label=script) for script in scripts],
            )


        return CompletionList(
            is_incomplete=False,
            items=[
                CompletionItem(label='configuration'),
                CompletionItem(label='healthcheck'),
                CompletionItem(label='debugging'),
                CompletionItem(label='infrastructure'),
                CompletionItem(label='inputs'),
                CompletionItem(label='source'),
                CompletionItem(label='kind'),
                CompletionItem(label='spec_version'),
            ]
        )
    elif '/services/' in params.text_document.uri:
        return CompletionList(
            is_incomplete=False,
            items=[
                CompletionItem(label='permissions'),
                CompletionItem(label='outputs'),
                CompletionItem(label='variables'),
                CompletionItem(label='module'),
                CompletionItem(label='inputs'),
                CompletionItem(label='source'),
                CompletionItem(label='kind'),
                CompletionItem(label='spec_version'),
            ]
        )
    else:
        return CompletionList(is_incomplete=True, items=[])


@colony_server.command(ColonyLanguageServer.CMD_COUNT_DOWN_BLOCKING)
def count_down_10_seconds_blocking(ls, *args):
    """Starts counting down and showing message synchronously.
    It will `block` the main thread, which can be tested by trying to show
    completion items.
    """
    for i in range(COUNT_DOWN_START_IN_SECONDS):
        ls.show_message(f'Counting down... {COUNT_DOWN_START_IN_SECONDS - i}')
        time.sleep(COUNT_DOWN_SLEEP_IN_SECONDS)


@colony_server.command(ColonyLanguageServer.CMD_COUNT_DOWN_NON_BLOCKING)
async def count_down_10_seconds_non_blocking(ls, *args):
    """Starts counting down and showing message asynchronously.
    It won't `block` the main thread, which can be tested by trying to show
    completion items.
    """
    for i in range(COUNT_DOWN_START_IN_SECONDS):
        ls.show_message(f'Counting down... {COUNT_DOWN_START_IN_SECONDS - i}')
        await asyncio.sleep(COUNT_DOWN_SLEEP_IN_SECONDS)


@colony_server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    _validate(ls, params)


@colony_server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: ColonyLanguageServer, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    server.show_message('Text Document Did Close')


@colony_server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    ls.show_message('Text Document Did Open')
    _validate(ls, params)


@colony_server.command(ColonyLanguageServer.CMD_REGISTER_COMPLETIONS)
async def register_completions(ls: ColonyLanguageServer, *args):
    """Register completions method on the client."""
    params = RegistrationParams(registrations=[
                Registration(
                    id=str(uuid.uuid4()),
                    method=COMPLETION,
                    register_options={"triggerCharacters": "[':']"})
             ])
    response = await ls.register_capability_async(params)
    if response is None:
        ls.show_message('Successfully registered completions method')
    else:
        ls.show_message('Error happened during completions registration.',
                        MessageType.Error)


@colony_server.command(ColonyLanguageServer.CMD_SHOW_CONFIGURATION_ASYNC)
async def show_configuration_async(ls: ColonyLanguageServer, *args):
    """Gets exampleConfiguration from the client settings using coroutines."""
    try:
        config = await ls.get_configuration_async(
            ConfigurationParams(items=[
                ConfigurationItem(
                    scope_uri='',
                    section=ColonyLanguageServer.CONFIGURATION_SECTION)
        ]))

        example_config = config[0].get('exampleConfiguration')

        ls.show_message(f'colonyServer.exampleConfiguration value: {example_config}')

    except Exception as e:
        ls.show_message_log(f'Error ocurred: {e}')


@colony_server.command(ColonyLanguageServer.CMD_SHOW_CONFIGURATION_CALLBACK)
def show_configuration_callback(ls: ColonyLanguageServer, *args):
    """Gets exampleConfiguration from the client settings using callback."""
    def _config_callback(config):
        try:
            example_config = config[0].get('exampleConfiguration')

            ls.show_message(f'colonyServer.exampleConfiguration value: {example_config}')

        except Exception as e:
            ls.show_message_log(f'Error ocurred: {e}')

    ls.get_configuration(ConfigurationParams(items=[
        ConfigurationItem(
            scope_uri='',
            section=ColonyLanguageServer.CONFIGURATION_SECTION)
    ]), _config_callback)


@colony_server.thread()
@colony_server.command(ColonyLanguageServer.CMD_SHOW_CONFIGURATION_THREAD)
def show_configuration_thread(ls: ColonyLanguageServer, *args):
    """Gets exampleConfiguration from the client settings using thread pool."""
    try:
        config = ls.get_configuration(ConfigurationParams(items=[
            ConfigurationItem(
                scope_uri='',
                section=ColonyLanguageServer.CONFIGURATION_SECTION)
        ])).result(2)

        example_config = config[0].get('exampleConfiguration')

        ls.show_message(f'colonyServer.exampleConfiguration value: {example_config}')

    except Exception as e:
        ls.show_message_log(f'Error ocurred: {e}')


@colony_server.command(ColonyLanguageServer.CMD_UNREGISTER_COMPLETIONS)
async def unregister_completions(ls: ColonyLanguageServer, *args):
    """Unregister completions method on the client."""
    params = UnregistrationParams(unregisterations=[
        Unregistration(id=str(uuid.uuid4()), method=COMPLETION)
    ])
    response = await ls.unregister_capability_async(params)
    if response is None:
        ls.show_message('Successfully unregistered completions method')
    else:
        ls.show_message('Error happened during completions unregistration.',
                        MessageType.Error)


@colony_server.feature(HOVER)
def hover(server: ColonyLanguageServer, params: TextDocumentPositionParams) -> Optional[Hover]:
    """Support Hover."""
    document = server.workspace.get_document(params.text_document.uri)
    # jedi_script = jedi_utils.script(server.project, document)
    # jedi_lines = jedi_utils.line_column(jedi_script, params.position)
    # markup_kind = _choose_markup(server)
    # for name in jedi_script.help(**jedi_lines):
    #     docstring = name.docstring()
    #     if not docstring:
    #         continue
    #     docstring_clean = jedi_utils.convert_docstring(docstring, markup_kind)
    #     contents = MarkupContent(kind=markup_kind, value=docstring_clean)
    #     document = server.workspace.get_document(params.text_document.uri)
    #     _range = pygls_utils.current_word_range(document, params.position)
    #     return Hover(contents=contents, range=_range)
    return Hover(contents="some content", range=Range(
                start=Position(line=31, character=1),
                end=Position(line=31, character=4),
            ))
    return None
