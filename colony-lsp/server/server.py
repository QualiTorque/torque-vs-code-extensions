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
from pygls.lsp import types
import yaml
import time
import uuid
import os
import glob
import pathlib
import re
from json import JSONDecodeError
from typing import Optional, Tuple, List

from pygls.lsp.methods import (CODE_LENS, COMPLETION, COMPLETION_ITEM_RESOLVE, DOCUMENT_LINK, TEXT_DOCUMENT_DID_CHANGE,
                               TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN, HOVER, REFERENCES, DEFINITION)
from pygls.lsp.types import (CompletionItem, CompletionList, CompletionOptions,
                             CompletionParams, ConfigurationItem,
                             ConfigurationParams, Diagnostic, Location,
                             DidChangeTextDocumentParams, Command,
                             DidCloseTextDocumentParams, Hover, TextDocumentPositionParams,
                             DidOpenTextDocumentParams, MessageType, Position,
                             Range, Registration, RegistrationParams,
                             Unregistration, UnregistrationParams, 
                             DocumentLink, DocumentLinkParams,
                             CodeLens, CodeLensOptions, CodeLensParams,
                             workspace, CompletionItemKind)
from pygls.server import LanguageServer
from pygls.workspace import Document, position_from_utf16

DEBOUNCE_DELAY = 0.3


COUNT_DOWN_START_IN_SECONDS = 10
COUNT_DOWN_SLEEP_IN_SECONDS = 1

APPLICATIONS = {}
SERVICES = {}

PREDEFINED_COLONY_INPUTS = [
    "$colony.environment.id",
    "$colony.environment.virtual_network_id",
    "$colony.environment.public_address"
]


class ColonyLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'colonyServer'

    def __init__(self):
        super().__init__()


colony_server = ColonyLanguageServer()


def _get_parent_word(document: Document, position: Position):
    lines = document.lines
    if position.line >= len(lines) or position.line == 0:
        return None

    row, col = position_from_utf16(lines, position)    
    
    cur_word = document.word_at_position(position=Position(line=row, character=col))
    line = lines[row]
    index = line.find(cur_word)
    if index >= 2:
        col = index - 2
    
    row -= 1
    word = None
    while row >= 0:
        word = document.word_at_position(position=Position(line=row, character=col))
        row -= 1
        if word:
            break
    
    return word
    

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


def _load_app_details(app_name: str, file_path: str):
    output = f"- {app_name}:\n"
    output += "  instances: 1\n"                        
    with open(file_path.replace("file://", ""), "r") as file:
        app_file = yaml.load(file, Loader=yaml.FullLoader)
        inputs = app_file['inputs'] if 'inputs' in app_file else None
        if inputs:
            output += "  input_values:\n"
            for input in inputs:
                if isinstance(input, str):
                    output += f"      - {input}: \n"
                elif isinstance(input, dict):
                    for k,v in input.items():
                        output += f"  - {k}: {v}\n"
    APPLICATIONS[app_name] = output


def _get_available_applications(root_folder: str):
    if APPLICATIONS:
        return APPLICATIONS
    else:
        apps_path = os.path.join(root_folder, 'applications')
        for dir in os.listdir(apps_path):
            app_dir = os.path.join(apps_path, dir)
            if os.path.isdir(app_dir):
                files = os.listdir(app_dir)
                if f'{dir}.yaml' in files:
                    _load_app_details(app_name=dir, file_path=os.path.join(app_dir, f'{dir}.yaml'))
                    
        return APPLICATIONS


def _load_service_details(srv_name: str, file_path: str):
    output = f"- {srv_name}:\n"
    with open(file_path.replace("file://", ""), "r") as file:
        app_file = yaml.load(file, Loader=yaml.FullLoader)
        inputs = app_file['inputs'] if 'inputs' in app_file else None
        if inputs:
            output += "  inputs_value:\n"
            for input in inputs:
                if isinstance(input, str):
                    output += f"  - {input}: \n"
                elif isinstance(input, dict):
                    for k,v in input.items():
                        output += f"  - {k}: {v}\n"
    SERVICES[srv_name] = output


def _get_available_services(root_folder: str):
    if SERVICES:
        return SERVICES
    else:
        srv_path = os.path.join(root_folder, 'services')
        for dir in os.listdir(srv_path):
            srv_dir = os.path.join(srv_path, dir)
            if os.path.isdir(srv_dir):
                files = os.listdir(srv_dir)
                if f'{dir}.yaml' in files:
                    _load_service_details(srv_name=dir, file_path=os.path.join(srv_dir, f'{dir}.yaml'))

        return SERVICES


def _get_app_scripts(app_dir_path: str):
    scripts = []
    files = pathlib.Path(app_dir_path.replace("file://", "")).parent.glob("./*")
    for file in files:
        if not file.name.endswith('.yaml'):
            scripts.append(pathlib.Path(file).name)

    return scripts


def _get_vars_from_tfvars(file_path: str):
    vars = []
    with open(file_path, "r") as f:
        content = f.read()
        vars = re.findall(r"(^.+?)\s*=", content, re.MULTILINE)
        
    return vars

def _get_service_vars(service_dir_path: str):
    with open(service_dir_path.replace("file://", ""), 'r') as stream:
        try:
            yaml_obj = yaml.load(stream, Loader=yaml.FullLoader) # todo: refactor
            doc_type = yaml_obj.get('kind', '')
        except yaml.YAMLError as exc:
            return []
    
    if doc_type == "TerraForm":
        tfvars = []
        files = pathlib.Path(service_dir_path.replace("file://", "")).parent.glob("./*")
        for file in files:
            if file.name.endswith('.tfvars'):
                item = {
                    "file": pathlib.Path(file).name,
                    "variables": _get_vars_from_tfvars(file)
                }
                tfvars.append(item)

        return tfvars
    
    return []


def _get_file_variables(source):
    vars = re.findall(r"(\$[\w\.\-]+)", source, re.MULTILINE)
    return vars  


def _get_file_inputs(source):
    yaml_obj = yaml.load(source, Loader=yaml.FullLoader) # todo: refactor
    inputs_obj = yaml_obj.get('inputs')
    inputs = []
    if inputs_obj:
        for input in inputs_obj:
            if isinstance(input, str):
                inputs.append(f"${input}")
            elif isinstance(input, dict):
                inputs.append(f"${list(input.keys())[0]}")
    
    return inputs


def _validate(ls, params):
    ls.show_message_log('Validating yaml...')

    text_doc = ls.workspace.get_document(params.text_document.uri)
    root = ls.workspace.root_path
    
    source = text_doc.source
    diagnostics = _validate_yaml(source) if source else []

    if not diagnostics: 
        yaml_obj = yaml.load(source, Loader=yaml.FullLoader) # todo: refactor
        doc_type = yaml_obj.get('kind', '')
        doc_lines = text_doc.lines
        file_inputs = _get_file_inputs(source)
        file_vars = _get_file_variables(source)
        # validate vars exist
        for var in file_vars:
            if var not in file_inputs:
                if (doc_type == "blueprint" and var.startswith('$colony')):
                    continue
                for i in range(len(doc_lines)):
                    col_pos = doc_lines[i].find(var)
                    if col_pos == -1:
                        continue
                    if var.startswith('$colony'):
                        msg = f"'{var}' is not an allowed variable in this file"
                    else:
                        msg = f"'{var}' is not defined"
                    d = Diagnostic(
                        range=Range(
                            start=Position(line=i, character=col_pos),
                            end=Position(line=i, character=col_pos + 1 +len(var))
                        ),
                        message=msg
                    )
                    diagnostics.append(d)

        if doc_type == "blueprint":
            apps = _get_available_applications(root)
            for app in yaml_obj.get('applications', []):
                app = list(app.keys())[0]
                if app not in apps.keys():
                    for i in range(len(doc_lines)):
                        col_pos = doc_lines[i].find(app)
                        if col_pos == -1:
                            continue
                        d = Diagnostic(
                            range=Range(
                                start=Position(line=i, character=col_pos),
                                end=Position(line=i, character=col_pos + 1 +len(app))
                            ),
                            message=f"Application '{app}' doesn't exist"
                        )
                        diagnostics.append(d)
            srvs = _get_available_services(root)
            for srv in yaml_obj.get('services', []):
                srv = list(srv.keys())[0]
                if srv not in srvs.keys():
                    for i in range(len(doc_lines)):
                        col_pos = doc_lines[i].find(srv)
                        if col_pos == -1:
                            continue
                        d = Diagnostic(
                            range=Range(
                                start=Position(line=i, character=col_pos),
                                end=Position(line=i, character=col_pos + 1 +len(srv))
                            ),
                            message=f"Service '{srv}' doesn't exist"
                        )
                        diagnostics.append(d)

        if doc_type == "application":
            scripts = _get_app_scripts(params.text_document.uri)
                
            for k, v in yaml_obj.get('configuration', []).items():
                script_ref = v.get('script', None)
                if script_ref and script_ref not in scripts:
                    for i in range(len(doc_lines)):
                        col_pos = doc_lines[i].find(script_ref)
                        if col_pos == -1:
                            continue
                        d = Diagnostic(
                            range=Range(
                                start=Position(line=i, character=col_pos),
                                end=Position(line=i, character=col_pos + 1 +len(script_ref))
                            ),
                            message=f"File {script_ref} doesn't exist"
                        )
                        diagnostics.append(d)
        elif doc_type == "TerraForm":            
            vars = _get_service_vars(params.text_document.uri)
            vars_files = [var["file"] for var in vars]

            for k, v in yaml_obj.get('variables', []).items():
                if k == "var_file" and v not in vars_files:
                    for i in range(len(doc_lines)):
                        col_pos = doc_lines[i].find(v)
                        if col_pos == -1:
                            continue
                        d = Diagnostic(
                            range=Range(
                                start=Position(line=i, character=col_pos),
                                end=Position(line=i, character=col_pos + 1 +len(v))
                            ),
                            message=f"File {v} doesn't exist"
                        )
                        diagnostics.append(d)
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


# @colony_server.feature(COMPLETION_ITEM_RESOLVE, CompletionOptions())
# def completion_item_resolve(server: ColonyLanguageServer, params: CompletionItem) -> CompletionItem:
#     """Resolves documentation and detail of given completion item."""
#     print('completion_item_resolve')
#     print(server)
#     print(params)
#     print('---------')
#     if params.label == 'debugging':
#         #completion = _MOST_RECENT_COMPLETIONS[item.label]
#         params.detail = "debugging description"
#         docstring = "some docstring" #convert_docstring(completion.docstring(), markup_kind)
#         params.documentation = "documention"  #MarkupContent(kind=markup_kind, value=docstring)
#         return params



# @colony_server.feature(COMPLETION, CompletionOptions(resolve_provider=True))
# def completions(params: Optional[CompletionParams] = None) -> CompletionList:
#     """Returns completion items."""
#     doc = colony_server.workspace.get_document(params.text_document.uri)
#     fdrs = colony_server.workspace.folders
#     root = colony_server.workspace.root_path
#     print('completion')
#     print(params)
#     print('--------')
    
#     if '/blueprints/' in params.text_document.uri:
#         parent = _get_parent_word(colony_server.workspace.get_document(params.text_document.uri), params.position)
#         items=[
#                 # CompletionItem(label='applications'),
#                 # CompletionItem(label='clouds'),
#                 # CompletionItem(label='debugging'),
#                 # CompletionItem(label='ingress'),
#                 # CompletionItem(label='availability'),
#             ]
        
#         if parent == "applications":
#             apps = _get_available_applications(root)
#             for app in apps:
#                 items.append(CompletionItem(label=app, kind=CompletionItemKind.Reference, insert_text=apps[app]))
        
#         if parent == "services":
#             srvs = _get_available_services(root)
#             for srv in srvs:
#                 items.append(CompletionItem(label=srv, kind=CompletionItemKind.Reference, insert_text=srvs[srv]))
        
#         if parent == "input_values":
#             available_inputs = _get_file_inputs(doc.source)
#             inputs = [CompletionItem(label=option, kind=CompletionItemKind.Variable) for option in available_inputs]
#             items.extend(inputs)
#             inputs = [CompletionItem(label=option, kind=CompletionItemKind.Variable) for option in PREDEFINED_COLONY_INPUTS]
#             items.extend(inputs)
#             # TODO: add output generated variables of apps/services in this blueprint ($colony.applications.app_name.outputs.output_name, $colony.services.service_name.outputs.output_name)
        
#         return CompletionList(
#             is_incomplete=False,
#             items=items
#         )
#     elif '/applications/' in params.text_document.uri:
#         words = _preceding_words(
#             colony_server.workspace.get_document(params.text_document.uri),
#             params.position)
#         # debug("words", words)
#         if words:
#             if words[0] == "script:":
#                 scripts = _get_app_scripts(params.text_document.uri)
#                 return CompletionList(
#                     is_incomplete=False,
#                     items=[CompletionItem(label=script) for script in scripts],
#                 )
#             elif words[0] in ["vm_size:", "instance_type:", "pull_secret:", "port:", "port-range:"]:
#                 available_inputs = _get_file_inputs(doc.source)
#                 return CompletionList(
#                     is_incomplete=False,
#                     items=[CompletionItem(label=option, kind=CompletionItemKind.Variable) for option in available_inputs],
#                 )
                
#         return CompletionList(
#             is_incomplete=False,
#             items=[
#                 #CompletionItem(label='configuration'),
#                 #CompletionItem(label='healthcheck'),
#                 #CompletionItem(label='debugging'),
#                 #CompletionItem(label='infrastructure'),
#                 #CompletionItem(label='inputs'),
#                 #CompletionItem(label='source'),
#                 #CompletionItem(label='kind'),
#                 #CompletionItem(label='spec_version'),
#             ]
#         )
#     elif '/services/' in params.text_document.uri:
#         words = _preceding_words(
#             colony_server.workspace.get_document(params.text_document.uri),
#             params.position)
#         # debug("words", words)
#         if words:
#             if words[0] == "var_file:":
#                 var_files = _get_service_vars(params.text_document.uri)
#                 return CompletionList(
#                     is_incomplete=False,
#                     items=[CompletionItem(label=var["file"],
#                                           insert_text=f"{var['file']}\r\nvalues:\r\n" + 
#                                                        "\r\n".join([f"  - {var_name}: " for var_name in var["variables"]])) for var in var_files],
#                                           kind=CompletionItemKind.File
#                 )
#             # TODO: when services should use inputs?
#             elif words[0] in ["vm_size:", "instance_type:", "pull_secret:", "port:", "port-range:"]:
#                 available_inputs = _get_file_inputs(doc.source)
#                 return CompletionList(
#                     is_incomplete=False,
#                     items=[CompletionItem(label=option, kind=CompletionItemKind.Variable) for option in available_inputs],
#                 )
                
#         # we don't need the below if we use a schema file 
#         return CompletionList(
#             is_incomplete=False,
#             items=[
#                 # CompletionItem(label='permissions'),
#                 # CompletionItem(label='outputs'),
#                 # CompletionItem(label='variables'),
#                 # CompletionItem(label='module'),
#                 # CompletionItem(label='inputs'),
#                 # CompletionItem(label='source'),
#                 # CompletionItem(label='kind'),
#                 # CompletionItem(label='spec_version'),
#             ]
#         )
#     else:
#         return CompletionList(is_incomplete=True, items=[])


# @colony_server.feature(DEFINITION)
# def goto_definition(server: ColonyLanguageServer, params: types.DeclarationParams):
#     uri = params.text_document.uri
#     doc = colony_server.workspace.get_document(uri)
#     words = _preceding_words(doc, params.position)
#         # debug("words", words)
#     if words[0].startswith("script"):
#         scripts = _get_app_scripts(params.text_document.uri)
#         return None
#         # return NoneCompletionList(
#         #     is_incomplete=False,
#         #     items=[CompletionItem(label=script) for script in scripts],
#         # )


# @colony_server.feature(CODE_LENS, CodeLensOptions(resolve_provider=False),)
# def code_lens(server: ColonyLanguageServer, params: Optional[CodeLensParams] = None) -> Optional[List[CodeLens]]:
#     print('------- code lens -----')
#     print(locals())
#     if '/applications/' in params.text_document.uri:
#         return [
#                     CodeLens(
#                         range=Range(
#                             start=Position(line=0, character=0),
#                             end=Position(line=1, character=1),
#                         ),
#                         command=Command(
#                             title='cmd1',
#                             command=ColonyLanguageServer.CMD_COUNT_DOWN_BLOCKING,
#                         ),
#                         data='some data 1',
#                     ),
#                     CodeLens(
#                         range=Range(
#                             start=Position(line=0, character=0),
#                             end=Position(line=1, character=1),
#                         ),
#                         command=Command(
#                             title='cmd2',
#                             command='',
#                         ),
#                         data='some data 2',
#                     ),
#                 ]
#     else:
#         return None


# @colony_server.feature(REFERENCES)
# async def lsp_references(server: ColonyLanguageServer, params: TextDocumentPositionParams,) -> List[Location]:
#     print('---- references ----')
#     print(locals())
#     references: List[Location] = []
#     l = Location(uri='file:///Users/yanivk/Projects/github/kalsky/samples/applications/empty-app/empty-app.yaml', 
#                  range=Range(
#                             start=Position(line=0, character=0),
#                             end=Position(line=1, character=1),
#                         ))
#     references.append(l)
#     l = Location(uri='file:///Users/yanivk/Projects/github/kalsky/samples/applications/mysql/mysql.yaml', 
#                  range=Range(
#                             start=Position(line=0, character=0),
#                             end=Position(line=1, character=1),
#                         ))
#     references.append(l)                          
#     return references


# @colony_server.feature(DOCUMENT_LINK)
# async def lsp_document_link(server: ColonyLanguageServer, params: DocumentLinkParams,) -> List[DocumentLink]:
#     print('---- document_link ----')
#     print(locals())
#     await asyncio.sleep(DEBOUNCE_DELAY)
#     links: List[DocumentLink] = []
    
#     links.append(DocumentLink(range=Range(
#                             start=Position(line=0, character=0),
#                             end=Position(line=1, character=1),
#                         ), target='file:///Users/yanivk/Projects/github/kalsky/samples/applications/mysql/mysql.sh'))
#     return links


# @colony_server.feature(HOVER)
# def hover(server: ColonyLanguageServer, params: TextDocumentPositionParams) -> Optional[Hover]:
#     print('---- hover ----')
#     print(locals())
#     document = server.workspace.get_document(params.text_document.uri)
#     return Hover(contents="some content", range=Range(
#                 start=Position(line=31, character=1),
#                 end=Position(line=31, character=4),
#             ))
#     return None


@colony_server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    print('------did change-------')
    _validate(ls, params)
    text_doc = ls.workspace.get_document(params.text_document.uri)
    root = ls.workspace.root_path
    
    source = text_doc.source
    yaml_obj = yaml.load(source, Loader=yaml.FullLoader) # todo: refactor
    doc_type = yaml_obj.get('kind', '')
    
    if doc_type == "application":
        app_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
        if APPLICATIONS and app_name not in APPLICATIONS: # if there is already a cache, add this file
            _load_app_details(app_name, params.text_document.uri)
    elif doc_type == "TerraForm":
        srv_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
        if SERVICES and srv_name not in SERVICES: # if there is already a cache, add this file
            _load_service_details(srv_name, params.text_document.uri)


@colony_server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: ColonyLanguageServer, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    server.show_message('Text Document Did Close')


@colony_server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    ls.show_message('Text Document Did Open')
    _validate(ls, params)

