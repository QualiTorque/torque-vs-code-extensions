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
import logging
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


class ColonyLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'colonyServer'
    latest_opened_document = None


colony_server = ColonyLanguageServer()


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
            cls_validator = ValidatorFactory.get_validator(tree)
            validator = cls_validator(tree, text_doc)
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
            source=type(colony_server).__name__
        )
        
        diagnostics.append(d)

    return diagnostics

@colony_server.feature(TEXT_DOCUMENT_DID_CHANGE)
def did_change(server: ColonyLanguageServer, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    if '/blueprints/' in params.text_document.uri or \
       '/applications/' in params.text_document.uri or \
       '/services/' in params.text_document.uri:
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


@colony_server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(server: ColonyLanguageServer, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    if '/blueprints/' in params.text_document.uri or \
       '/applications/' in params.text_document.uri or \
       '/services/' in params.text_document.uri:
        server.latest_opened_document = params.text_document
        server.show_message('Detected a Colony file', msg_type=MessageType.Log)
        server.workspace.put_document(params.text_document)
        _validate(server, params)



@colony_server.feature(WORKSPACE_DID_CHANGE_WATCHED_FILES)
async def workspace_changed(server: ColonyLanguageServer, params: DidChangeWorkspaceFoldersParams):
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
    
#     return None


@colony_server.feature(COMPLETION, CompletionOptions(resolve_provider=False))
def completions(params: Optional[CompletionParams] = None) -> CompletionList:
    """Returns completion items."""
    doc = colony_server.workspace.get_document(params.text_document.uri)
    
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
            inputs_names_list.append("colony")

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

    root = colony_server.workspace.root_path
    
    if doc_type == "blueprint":
        items=[]
        if last_word.endswith('.'):
            if words and len(words) > 1 and words[1] == words[-1] and words[0] != '-':
                cur_word = words[-1]
                word_parts = cur_word.split('$')
                if word_parts:
                    if word_parts[-1].startswith('{colony.'):
                        cur_word = word_parts[-1][1:]
                    elif word_parts[-1].startswith('colony.'):
                        cur_word = word_parts[-1]
                    else:
                        cur_word = ''
                if cur_word:
                    options = []
                    if cur_word.startswith('colony'):
                        if cur_word == 'colony.':
                            options = ['environment', 'repos']
                            if tree.applications and len(tree.applications.nodes) > 0:
                                options.append('applications')
                            if tree.services and len(tree.services.nodes) > 0:
                                options.append('services')
                        elif cur_word == 'colony.environment.':
                            options = ['id', 'virtual_network_id', 'public_address']
                        elif cur_word == 'colony.repos.':
                            options = ['current']
                        elif cur_word == 'colony.repos.current.':
                            options = ['branch']
                        elif cur_word.startswith('colony.repos.'):
                            parts = cur_word.split('.')
                            if len(parts) == 4 and parts[2] != '':
                                options = ["token", "url"]
                        elif cur_word == 'colony.applications.':
                            for app in tree.get_applications():
                                options.append(app.id.text)
                        elif cur_word == 'colony.services.':
                            for srv in tree.get_services():
                                options.append(srv.id.text)
                        elif cur_word.startswith('colony.applications.'):
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
                        elif cur_word.startswith('colony.services.'):
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
#                     # CodeLens(
#                     #     range=Range(
#                     #         start=Position(line=0, character=0),
#                     #         end=Position(line=1, character=1),
#                     #     ),
#                     #     command=Command(
#                     #         title='cmd1',
#                     #         command=ColonyLanguageServer.CMD_COUNT_DOWN_BLOCKING,
#                     #     ),
#                     #     data='some data 1',
#                     # ),
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


@colony_server.feature(DOCUMENT_LINK)
async def lsp_document_link(server: ColonyLanguageServer, params: DocumentLinkParams,) -> List[DocumentLink]:
    await asyncio.sleep(DEBOUNCE_DELAY)
    links: List[DocumentLink] = []
    
    doc = colony_server.workspace.get_document(params.text_document.uri)
    try:
        yaml_obj = yaml.load(doc.source, Loader=yaml.FullLoader)
        if yaml_obj:
            doc_type = yaml_obj.get('kind', '')
        else:
            return links
    except yaml.MarkedYAMLError as ex:
        return links
    
    root = colony_server.workspace.root_path        
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


# @colony_server.feature(TEXT_DOCUMENT_SEMANTIC_TOKENS)
#             #            , SemanticTokensOptions(
#             #     # work_done_progress=True,
#             #     legend=SemanticTokensLegend(
#             #         token_types=['colonyVariable'],
#             #         token_modifiers=[]
#             #     ),
#             #     # range=False,
#             #     # full=True
#             #     # full={"delta": True}
#             # ))
# def semantic_tokens_range(server: ColonyLanguageServer, params: SemanticTokensParams) -> Optional[Union[SemanticTokens, SemanticTokensPartialResult]]:
#     print('---- TEXT_DOCUMENT_SEMANTIC_TOKENS_RANGE ----')
#     print(locals())
#     # document = server.workspace.get_document(params.text_document.uri)
#     # return Hover(contents="some content", range=Range(
#     #             start=Position(line=31, character=1),
#     #             end=Position(line=31, character=4),
#     #         ))
#     return None
