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
from dataclasses import dataclass
import json
import logging
import subprocess
import sys
import textwrap
import tabulate

from server.ats.trees.app import AppTree

from server.ats.trees.common import BaseTree, PropertyNode
from server.utils.common import is_var_allowed
from server.validation.factory import ValidatorFactory

from pygls.lsp.types.language_features.completion import CompletionTriggerKind, InsertTextMode

# from pygls.lsp.types.language_features.semantic_tokens import SemanticTokens, SemanticTokensEdit, SemanticTokensLegend, SemanticTokensOptions, SemanticTokensParams, SemanticTokensPartialResult, SemanticTokensRangeParams
from pygls.lsp import types
from pygls.lsp.types.basic_structures import TextDocumentItem, TextEdit, VersionedTextDocumentIdentifier
from pygls.lsp import types, InitializeResult
import yaml
import time
import uuid
import os
import glob
import re
import pathlib
from json import JSONDecodeError
from typing import Any, Dict, Optional, Tuple, List, Union, cast

from server.ats.parser import   BlueprintTree, Parser, ParserError

from server.utils import services, applications, common
from pygls.protocol import LanguageServerProtocol

from pygls.lsp.methods import (CODE_LENS, COMPLETION, COMPLETION_ITEM_RESOLVE, DOCUMENT_LINK, TEXT_DOCUMENT_DID_CHANGE,
                               TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN, HOVER, REFERENCES, DEFINITION, 
                               TEXT_DOCUMENT_SEMANTIC_TOKENS, TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL, TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL_DELTA, WORKSPACE_DID_CHANGE_WATCHED_FILES)
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
                             workspace, CompletionItemKind, DidChangeWorkspaceFoldersParams)
from pygls.server import LanguageServer
from pygls.workspace import Document, Workspace, position_from_utf16

DEBOUNCE_DELAY = 0.3


class TorqueLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'torque'
    CMD_VALIDATE_BLUEPRINT = 'validate_torque_blueprint'
    CMD_START_SANDBOX = 'start_torque_sandbox'
    latest_opened_document = None


torque_ls = TorqueLanguageServer()

def _is_torque_file(file_uri):
    return '/blueprints/' in file_uri or '/applications/' in file_uri or '/services/' in file_uri


def _diagnose_tree_errors(tree: BaseTree) -> list:
    diagnostics = []
    for error in tree.errors:
        d = Diagnostic(
            range=Range(
                start=Position(line=error.start_pos[0], character=error.start_pos[1]),
                end=Position(line=error.end_pos[0], character=error.end_pos[1])
            ),
            message=error.message)
        diagnostics.append(d)
    return diagnostics


def _validate(ls, params):
    text_doc = ls.workspace.get_document(params.text_document.uri)

    source = text_doc.source
    diagnostics = _validate_yaml(source) if source else []

    if not diagnostics:
        try:
            tree = Parser(source).parse()
            diagnostics += _diagnose_tree_errors(tree)
            validator = ValidatorFactory.get_validator(tree, text_doc)
            diagnostics += validator.validate()
        except ParserError as e:
            diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=e.start_pos[0], character=e.start_pos[1]),
                        end=Position(line=e.end_pos[0], character=e.end_pos[1])),
                    message=e.message))
        except ValueError as e:
            diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=0)),
                    message=str(e)))
        except Exception as ex:
            import sys
            print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)

    ls.publish_diagnostics(text_doc.uri, diagnostics)


def _validate_yaml(source):
    """Validates yaml file."""
    diagnostics = []

    try:
        yaml.load(source, Loader=yaml.FullLoader)
    except yaml.MarkedYAMLError as ex:
        mark = ex.problem_mark
        d = Diagnostic(
            range=Range(
                start=Position(line=mark.line - 1, character=mark.column - 1),
                end=Position(line=mark.line - 1, character=mark.column)
            ),
            message=ex.problem,
            source=type(torque_ls).__name__
        )
        
        diagnostics.append(d)

    return diagnostics

@torque_ls.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(server: TorqueLanguageServer, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    if _is_torque_file(params.text_document.uri):
        _validate(server, params)
        text_doc = server.workspace.get_document(params.text_document.uri)
        
        source = text_doc.source
        yaml_obj = yaml.load(source, Loader=yaml.FullLoader) # todo: refactor
        doc_type = yaml_obj.get('kind', '')
        
        if doc_type == "application":
            app_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
            applications.reload_app_details(app_name=app_name, app_source=source)
            
        elif doc_type == "TerraForm":
            srv_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
            services.reload_service_details(srv_name, srv_source=source)


@torque_ls.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(server: TorqueLanguageServer, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    if _is_torque_file(params.text_document.uri):
        server.latest_opened_document = params.text_document
        server.show_message('Detected a Torque file', msg_type=MessageType.Log)
        server.workspace.put_document(params.text_document)
        _validate(server, params)



@torque_ls.feature(WORKSPACE_DID_CHANGE_WATCHED_FILES)
async def workspace_changed(server: TorqueLanguageServer, params: DidChangeWorkspaceFoldersParams):
    """Workspace changed notification."""
    current_file_changed = False
    for change in params.changes:
        if change.uri != server.latest_opened_document.uri:
            if '/applications/' in change.uri or '/services/' in change.uri:        
                if change.type != workspace.FileChangeType.Deleted:
                    text_doc = server.workspace.get_document(change.uri)
                    source = text_doc.source
                    yaml_obj = yaml.load(source, Loader=yaml.FullLoader) # todo: refactor
                    doc_type = yaml_obj.get('kind', '')
                    
                    if doc_type == "application":
                        app_name = pathlib.Path(change.uri).name.replace(".yaml", "")
                        applications.reload_app_details(app_name=app_name, app_source=source)
                        
                    elif doc_type == "TerraForm":
                        srv_name = pathlib.Path(change.uri).name.replace(".yaml", "")
                        services.reload_service_details(srv_name, srv_source=source)
                else:
                    if '/applications/' in change.uri:
                        app_name = pathlib.Path(change.uri).name.replace(".yaml", "")
                        applications.remove_app_details(app_name=app_name)
                        
                    elif '/services/' in change.uri:
                        srv_name = pathlib.Path(change.uri).name.replace(".yaml", "")
                        services.remove_service_details(srv_name)
        else:
            current_file_changed = True
    try:
        if '/blueprints/' in server.latest_opened_document.uri and not current_file_changed:
            print('validating')
            _validate(server, DidOpenTextDocumentParams(text_document=server.latest_opened_document))
    except Exception as ex:
        logging.error(ex)


# @torque_ls.feature(COMPLETION_ITEM_RESOLVE, CompletionOptions())
# def completion_item_resolve(server: TorqueLanguageServer, params: CompletionItem) -> CompletionItem:
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
    
#     return None


@torque_ls.feature(COMPLETION, CompletionOptions(resolve_provider=False))
def completions(params: Optional[CompletionParams] = None) -> CompletionList:
    """Returns completion items."""
    if not _is_torque_file(params.text_document.uri):
        return CompletionList(is_incomplete=True, items=[])
    
    doc = torque_ls.workspace.get_document(params.text_document.uri)
    
    try:
        yaml_obj = yaml.load(doc.source, Loader=yaml.FullLoader)
        if yaml_obj:
            doc_type = yaml_obj.get('kind', '')
        else:
            return CompletionList(is_incomplete=True, items=[])
    except yaml.MarkedYAMLError as ex:
        return CompletionList(is_incomplete=True, items=[])

    tree = Parser(doc.source).parse()
    words = common.preceding_words(doc, params.position)
    last_word = words[-1] if words else ""
    
    if last_word.endswith('$') or last_word.endswith(':'):
        if is_var_allowed(tree, params.position):
            inputs_names_list = [i_node.key.text for i_node in tree.get_inputs()]
            if doc_type == "blueprint":
                inputs_names_list.append("torque")

            line = params.position.line
            char = params.position.character
            suggested_vars = [
                CompletionItem(label=f"${var}", 
                                kind=CompletionItemKind.Variable,
                                text_edit=TextEdit(
                                    range=Range(start=Position(line=line, character=char-(1 if last_word.endswith('$') else 0)),
                                                end=Position(line=line, character=char)),
                                    new_text=f"${var}" if last_word == '$' or last_word.endswith(':') else f"${{{var}}}",
                                ))
                for var in inputs_names_list]

            return CompletionList(is_incomplete=(len(suggested_vars)==0), items=suggested_vars)

    root = torque_ls.workspace.root_path
    
    if doc_type == "blueprint":
        items=[]
        if last_word.endswith('.'):
            if words and len(words) > 1 and words[1] == words[-1] and words[0] != '-':
                cur_word = words[-1]
                word_parts = cur_word.split('$')
                if word_parts:
                    if word_parts[-1].startswith('{torque.'):
                        cur_word = word_parts[-1][1:]
                    elif word_parts[-1].startswith('torque.'):
                        cur_word = word_parts[-1]
                    else:
                        cur_word = ''
                if cur_word:
                    options = []
                    if cur_word.startswith('torque'):
                        if cur_word == 'torque.':
                            options = ['environment', 'repos']
                            if tree.applications and len(tree.applications.nodes) > 0:
                                options.append('applications')
                            if tree.services and len(tree.services.nodes) > 0:
                                options.append('services')
                        elif cur_word == 'torque.environment.':
                            options = ['id', 'virtual_network_id', 'public_address']
                        elif cur_word == 'torque.repos.':
                            options = ['current']
                        elif cur_word == 'torque.repos.current.':
                            options = ['branch']
                        elif cur_word.startswith('torque.repos.'):
                            parts = cur_word.split('.')
                            if len(parts) == 4 and parts[2] != '':
                                options = ["token", "url"]
                        elif cur_word == 'torque.applications.':
                            for app in tree.get_applications():
                                options.append(app.id.text)
                        elif cur_word == 'torque.services.':
                            for srv in tree.get_services():
                                options.append(srv.id.text)
                        elif cur_word.startswith('torque.applications.'):
                            parts = cur_word.split('.')
                            if len(parts) == 4 and parts[2] != '':
                                options = ['outputs', 'dns']
                            elif len(parts) == 5 and parts[3] == 'outputs':
                                apps = applications.get_available_applications(root)
                                for app in apps:
                                    if app == parts[2]:
                                        outputs = applications.get_app_outputs(app_name=parts[2])
                                        if outputs:
                                            options.extend(outputs)
                                        break
                        elif cur_word.startswith('torque.services.'):
                            parts = cur_word.split('.')
                            if len(parts) == 4 and parts[2] != '':
                                options.append('outputs')
                            elif len(parts) == 5 and parts[3] == 'outputs':
                                apps = services.get_available_services(root)
                                for app in apps:
                                    if app == parts[2]:
                                        outputs = services.get_service_outputs(srv_name=parts[2])
                                        if outputs:
                                            options.extend(outputs)
                                        break
    
                    line = params.position.line
                    char = params.position.character
                    for option in options:
                        if option in ["applications", "services", "environment", "repos", "current", "outputs"]:
                            command = Command(command="editor.action.triggerSuggest", title=option)                            
                        else:
                            command = None
                        items.append(CompletionItem(label=option,
                                                    command=command,
                                                    kind=CompletionItemKind.Property,
                                                    text_edit=TextEdit(
                                                        range=Range(start=Position(line=line, character=char),
                                                                    end=Position(line=line, character=char+len(option))),
                                                                    new_text=option + ("." if command else "")
                                                    )))
    
        else:
            parent = common.get_parent_word(doc, params.position)
            line = params.position.line
            char = params.position.character
    
            if parent == "applications":
                apps = applications.get_available_applications(root)
                for app in apps:
                    if apps[app]['app_completion']:
                        items.append(CompletionItem(label=app,
                                                    kind=CompletionItemKind.Reference,
                                                    text_edit=TextEdit(
                                                                    range=Range(start=Position(line=line, character=char-2),
                                                                                end=Position(line=line, character=char)),
                                                                    new_text=apps[app]['app_completion'],
                                                    )))
    
            if parent == "services":
                srvs = services.get_available_services(root)
                for srv in srvs:
                    if srvs[srv]['srv_completion']:
                        items.append(CompletionItem(label=srv,
                                                    kind=CompletionItemKind.Reference,
                                                    text_edit=TextEdit(
                                                                    range=Range(start=Position(line=line, character=char-2),
                                                                                end=Position(line=line, character=char)),
                                                                    new_text=srvs[srv]['srv_completion'],
                                                    )))
        
        if items:
            return CompletionList(
                is_incomplete=False,
                items=items
            )
        else:
            line = params.position.line
            char = params.position.character
            return CompletionList(is_incomplete=False, 
                                  items=[CompletionItem(label=f"No suggestions.", 
                                                        kind=CompletionItemKind.Text, 
                                                        text_edit=TextEdit(new_text="", 
                                                                           range=Range(start=Position(line=line, character=char-(1 if last_word.endswith('$') else 0)),
                                                                                       end=Position(line=line, character=char))))])
    elif doc_type == "application":
        if words and len(words) == 1:
            if words[0] == "script:":
                scripts = applications.get_app_scripts(params.text_document.uri)
                return CompletionList(
                    is_incomplete=False,
                    items=[CompletionItem(label=script,
                                          kind=CompletionItemKind.File) for script in scripts],
                )
    
    if doc_type == "TerraForm":
        if words and len(words) == 1:
            if words[0] == "var_file:":
                var_files = services.get_service_vars(params.text_document.uri)
                return CompletionList(
                    is_incomplete=False,
                    items=[CompletionItem(label=var["file"],
                                          insert_text=f"{var['file']}\r\nvalues:\r\n" +
                                                       "\r\n".join([f"  - {var_name}: " for var_name in var["variables"]])) for var in var_files],
                                          kind=CompletionItemKind.File
                )            
    
    else:
        line = params.position.line
        char = params.position.character
        return CompletionList(is_incomplete=False, 
                                items=[CompletionItem(label=f"No suggestions.", 
                                                    kind=CompletionItemKind.Text, 
                                                    text_edit=TextEdit(new_text="", 
                                                                        range=Range(start=Position(line=line, character=char-(1 if last_word.endswith('$') else 0)),
                                                                                    end=Position(line=line, character=char))))])        


# @torque_ls.feature(DEFINITION)
# def goto_definition(server: TorqueLanguageServer, params: types.DeclarationParams):
#     uri = params.text_document.uri
#     doc = torque_ls.workspace.get_document(uri)
#     words = _preceding_words(doc, params.position)
#         # debug("words", words)
#     if words[0].startswith("script"):
#         scripts = _get_app_scripts(params.text_document.uri)
#         return None
#         # return NoneCompletionList(
#         #     is_incomplete=False,
#         #     items=[CompletionItem(label=script) for script in scripts],
#         # )


@torque_ls.feature(CODE_LENS, CodeLensOptions(resolve_provider=False),)
def code_lens(server: TorqueLanguageServer, params: Optional[CodeLensParams] = None) -> Optional[List[CodeLens]]:
    if '/blueprints/' in params.text_document.uri:
        doc = torque_ls.workspace.get_document(params.text_document.uri)
        try:
            bp_tree = Parser(doc.source).parse()            
        except Exception as ex:
            import sys
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            return None
        
        inputs = []
        bp_inputs = bp_tree.get_inputs()
        for inp in bp_inputs:
            inputs.append({"name": inp.key.text, 
                           "default_value": inp.default_value.text if inp.default_value else "",
                           "optional": True if inp.value and hasattr(inp.value, 'optional') and inp.value.optional else False,
                           "display_style": 'masked' if inp.value and hasattr(inp.value, 'display_style') and inp.value.display_style and inp.value.display_style.text else 'text',
                           })            
                
                
        return [
                    CodeLens(
                        range=Range(
                            start=Position(line=0, character=0),
                            end=Position(line=1, character=1),
                        ),
                        command=Command(
                            title='Validate on Server',
                            command=TorqueLanguageServer.CMD_VALIDATE_BLUEPRINT,
                            arguments=[params.text_document.uri]
                        )
                    ),
                    CodeLens(
                        range=Range(
                            start=Position(line=0, character=0),
                            end=Position(line=1, character=1),
                        ),
                        command=Command(
                            title='Start Sandbox',
                            # command=TorqueLanguageServer.CMD_START_SANDBOX,
                            # arguments=[params.text_document.uri]
                            command="extension.openReserveForm",
                            arguments=[params.text_document.uri, 30, inputs]
                        )
                    ),
                ]
    else:
        return None


# @torque_ls.feature(REFERENCES)
# async def lsp_references(server: TorqueLanguageServer, params: TextDocumentPositionParams,) -> List[Location]:
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


@torque_ls.feature(DOCUMENT_LINK)
async def lsp_document_link(server: TorqueLanguageServer, params: DocumentLinkParams,) -> List[DocumentLink]:
    links: List[DocumentLink] = []    
    if not _is_torque_file(params.text_document.uri):
        return links
    
    await asyncio.sleep(DEBOUNCE_DELAY)
    
    doc = torque_ls.workspace.get_document(params.text_document.uri)
    try:
        yaml_obj = yaml.load(doc.source, Loader=yaml.FullLoader)
        if yaml_obj:
            doc_type = yaml_obj.get('kind', '')
        else:
            return links
    except yaml.MarkedYAMLError as ex:
        return links

    root = torque_ls.workspace.root_path

    if doc_type == "blueprint":
        try:
            bp_tree = Parser(doc.source).parse()            
        except Exception as ex:
            import sys
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            return links
        
        for app in bp_tree.get_applications():
            target_path = os.path.join(root, "applications", app.id.text, app.id.text+".yaml")
            if os.path.exists(target_path) and os.path.isfile(target_path):
                tooltip = "Open the application file at " + target_path
                links.append(DocumentLink(range=Range(
                                            start=Position(line=app.id.start_pos[0], character=app.id.start_pos[1]),
                                            end=Position(line=app.id.start_pos[0], character=app.start_pos[1]+len(app.id.text))),
                                            target=pathlib.Path(target_path).as_uri(),
                                            tooltip=tooltip))
        
        for srv in bp_tree.get_services():
            target_path = os.path.join(root, "services", srv.id.text, srv.id.text+".yaml")
            if os.path.exists(target_path) and os.path.isfile(target_path):
                tooltip = "Open the service file at " + target_path
                links.append(DocumentLink(range=Range(
                                            start=Position(line=srv.id.start_pos[0], character=srv.id.start_pos[1]),
                                            end=Position(line=srv.id.start_pos[0], character=srv.start_pos[1]+len(srv.id.text))),
                                            target=pathlib.Path(target_path).as_uri(),
                                            tooltip=tooltip))
    
    elif doc_type == "application":
        try:
            app_tree: AppTree = Parser(doc.source).parse()        
            app_name = doc.filename.replace('.yaml', '')    
        except Exception as ex:
            import sys
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            return links
        
        if app_tree.configuration:
            for state in ['healthcheck', 'initialization', 'start']:
                state_block = getattr(app_tree.configuration, state, None)

                if state_block is None or state_block.script is None:
                    continue

                script: PropertyNode = state_block.script
                if not script.value:
                    continue

                file_name = script.text
                target_path = os.path.join(root, "applications", app_name, file_name)
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    tooltip = "Open the script file at " + target_path
                    links.append(DocumentLink(
                        range=Range(
                            start=Position(line=script.value.start_pos[0], character=script.value.start_pos[1]),
                            end=Position(line=script.value.start_pos[0], character=script.value.start_pos[1]+len(script.text))), 
                        target=pathlib.Path(target_path).as_uri(), 
                        tooltip=tooltip))

    elif doc_type == "TerraForm":
        try:
            srv_tree = Parser(doc.source).parse()        
            srv_name = doc.filename.replace('.yaml', '')    
        except Exception as ex:
            import sys
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            return links
        
        if srv_tree.variables:
            script: PropertyNode = srv_tree.variables.var_file
            if script and script.value:
                file_name = script.text
                target_path = os.path.join(root, "services", srv_name, file_name)
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    tooltip = "Open the variables file at " + target_path
                    links.append(DocumentLink(
                                    range=Range(
                                        start=Position(line=script.value.start_pos[0], character=script.value.start_pos[1]),
                                        end=Position(line=script.value.start_pos[0], character=script.value.start_pos[1]+len(script.text))), 
                                    target=pathlib.Path(target_path).as_uri(), 
                                    tooltip=tooltip))             
    
    return links


# @torque_ls.feature(HOVER)
# def hover(server: TorqueLanguageServer, params: TextDocumentPositionParams) -> Optional[Hover]:
#     print('---- hover ----')
#     print(locals())
#     document = server.workspace.get_document(params.text_document.uri)
#     return Hover(contents="some content", range=Range(
#                 start=Position(line=31, character=1),
#                 end=Position(line=31, character=4),
#             ))
#     return None


# @torque_ls.feature(TEXT_DOCUMENT_SEMANTIC_TOKENS)
#             #            , SemanticTokensOptions(
#             #     # work_done_progress=True,
#             #     legend=SemanticTokensLegend(
#             #         token_types=['torqueVariable'],
#             #         token_modifiers=[]
#             #     ),
#             #     # range=False,
#             #     # full=True
#             #     # full={"delta": True}
#             # ))
# def semantic_tokens_range(server: TorqueLanguageServer, params: SemanticTokensParams) -> Optional[Union[SemanticTokens, SemanticTokensPartialResult]]:
#     print('---- TEXT_DOCUMENT_SEMANTIC_TOKENS_RANGE ----')
#     print(locals())
#     # document = server.workspace.get_document(params.text_document.uri)
#     # return Hover(contents="some content", range=Range(
#     #             start=Position(line=31, character=1),
#     #             end=Position(line=31, character=4),
#     #         ))
#     return None


@torque_ls.command(TorqueLanguageServer.CMD_START_SANDBOX)
async def start_sandbox(server: TorqueLanguageServer, *args):
    if len(args[0]) == 0:
        server.show_message('Please start the sandbox from the command in the blueprint file.', MessageType.Error)
        return

    try:
        config = await server.get_configuration_async(ConfigurationParams(items=[
                ConfigurationItem(
                    scope_uri='',
                    section=TorqueLanguageServer.CONFIGURATION_SECTION)
                ]))
        connections = config[0].get('connections')
    except:
        server.show_message('Please define your connections in the settings first.', MessageType.Error)
        return

    connection = None
    if len(connections) == 1:
        connection = connections[0]
    else:
        for con in connections:
            if "default" in con and con["default"] == True:
                connection = con
                break

    blueprint_name = args[0][0]
    dev_mode = False
    if blueprint_name.endswith(".yaml"):
        dev_mode = True
        blueprint_name = pathlib.Path(args[0][0]).name.replace(".yaml", "")
        duration = 30
        inputs = ""
    else:
        duration = args[0][1]
        inputs_args = args[0][2]
        if inputs_args:
            idx = 0
            inputs = ""
            for inp in list(inputs_args._fields):
                inputs += inp + "=" + inputs_args[idx] + ", "
                idx += 1
            inputs = inputs[:-2]
        else:
            inputs = ""            
        
    account = connection["account"]
    space = connection["space"]
    token = connection["token"]
    server.show_message('Starting sandbox from blueprint: ' + blueprint_name)
    try:
        command = [sys.prefix + '/bin/colony',
                                    '--token', token,
                                    '--account', account,
                                    '--space', space,
                                    'sb', 'start', blueprint_name, '-d', duration]
        if inputs:
            command.extend(['-i', inputs])
        # if not dev_mode:
        #     command.extend(['-w', '0'])
        process = subprocess.Popen(command,
                                   cwd=server.workspace.root_path,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for line in process.stdout:
            line_dec = line.decode().strip()
            if not line_dec.endswith('sec]'):
                server.show_message_log(line_dec)

        error_msg = ""
        if process.stderr:
            # server.show_message_log('Error while starting the sandbox:')
            for line in process.stderr:
                error_msg += line.decode().strip() + '\n'
                # server.show_message_log(line.decode().strip())
            if error_msg:
                error_msg = 'Error while starting the sandbox:\n' + error_msg
                server.show_message_log(error_msg)
        if error_msg:
            server.show_message('Sandbox had some errors. See details in the Output view.')
        else:
            server.show_message('Sandbox is ready. See details in the Output view.')
    except Exception as ex:
        server.show_message_log(str(ex), msg_type=MessageType.Error)


@torque_ls.command(TorqueLanguageServer.CMD_VALIDATE_BLUEPRINT)
async def validate_blueprint(server: TorqueLanguageServer, *args):
    if len(args[0]) == 0:
        server.show_message('Please validate the blueprint from the command in the blueprint file.', MessageType.Error)
        return

    try:
        config = await server.get_configuration_async(ConfigurationParams(items=[
                ConfigurationItem(
                    scope_uri='',
                    section=TorqueLanguageServer.CONFIGURATION_SECTION)
                ]))
        connections = config[0].get('connections')
    except:
        server.show_message('Please define your connections in the settings first.', MessageType.Error)
        return

    if len(connections) == 1:
        connection = connections[0]
    else:
        for con in connections:
            if "default" in con and con["default"].lower() == "true":
                connection = con
                break

    blueprint_name = pathlib.Path(args[0][0]).name.replace(".yaml", "")
    account = connection["account"]
    space = connection["space"]
    token = connection["token"]
    server.show_message('Validating blueprint: ' + blueprint_name)

    try:
        result = subprocess.run([sys.prefix + '/bin/colony',
                                '--token', token,
                                '--account', account,
                                '--space', space,
                                'bp', 'validate', blueprint_name],
                                cwd=server.workspace.root_path,
                                capture_output=True, text=True)
    except Exception as ex:
        print(ex)
    if result.stderr:
        lines = result.stderr.split('\n')
        table = []
        headers = ["Name", "Message"]
        for line in lines[3:-1]:
            #cols = line.split('  ')
            cols = re.split(r'\s{2,}', line)
            table.append(['\n'.join(textwrap.wrap(cols[0], width=40)),
                          '\n'.join(textwrap.wrap(cols[1], width=60))])

        server.show_message_log(tabulate.tabulate(table, headers, tablefmt="simple"))
        server.show_message('Validation complete. Check the Problems view for any issues.')
    else:
        server.show_message('Validation completed. Blueprint is valid.')

