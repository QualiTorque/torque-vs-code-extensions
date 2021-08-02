import asyncio
from dataclasses import dataclass
import logging
import subprocess
import sys

# from pygls.lsp.types.language_features.semantic_tokens import SemanticTokens, SemanticTokensEdit, SemanticTokensLegend, SemanticTokensOptions, SemanticTokensParams, SemanticTokensPartialResult, SemanticTokensRangeParams
from server.utils.validation import AppValidationHandler, BlueprintValidationHandler, ServiceValidationHandler
from pygls.lsp import types
from pygls.lsp.types.basic_structures import VersionedTextDocumentIdentifier
from pygls.lsp import types, InitializeResult
import yaml
import time
import uuid
import os
import glob
import pathlib
import re
from json import JSONDecodeError
from typing import Any, Dict, Optional, Tuple, List, Union, cast

from server.ats.parser import AppParser, BlueprintParser, BlueprintTree, ServiceParser

from server.utils import services, applications, common
from pygls.protocol import LanguageServerProtocol

from pygls.lsp.methods import (CODE_LENS, COMPLETION, COMPLETION_ITEM_RESOLVE, DOCUMENT_LINK, TEXT_DOCUMENT_DID_CHANGE,
                               TEXT_DOCUMENT_DID_CLOSE, TEXT_DOCUMENT_DID_OPEN, HOVER, REFERENCES, DEFINITION, 
                               TEXT_DOCUMENT_SEMANTIC_TOKENS)
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
from pygls.workspace import Document, Workspace, position_from_utf16

DEBOUNCE_DELAY = 0.3



# class ColonyWorkspace(Workspace):
#     """
#     Add colony-specific properties
#     """

#     def __init__(self, root_uri, sync_kind, workspace_folders):
#         self._colony_objs = {}

#         super().__init__(root_uri, sync_kind=sync_kind, workspace_folders=workspace_folders)

#     @property
#     def colony_objs(self):
#         return self._colony_objs

#     def _update_document(self, text_document: Union[types.TextDocumentItem, types.VersionedTextDocumentIdentifier]) -> None:
#         self.logger.debug("updating document '%s'", text_document.uri)
#         uri = text_document.uri
#         colony_obj = yaml.load(self.get_document(uri).source, Loader=yaml.FullLoader)
#         self._colony_objs[uri] = colony_obj

#     def update_document(self, text_doc: VersionedTextDocumentIdentifier, change: workspace.TextDocumentContentChangeEvent):
#         super().update_document(text_doc, change)
#         self._update_document(text_doc)

#     def put_document(self, text_document: types.TextDocumentItem) -> None:
#         super().put_document(text_document)
#         self._update_document(text_document)


# class ColonyLspProtocol(LanguageServerProtocol):
#     """Custom protocol that replaces the workspace with a ColonyWorkspace
#     instance.
#     """

#     workspace: ColonyWorkspace

#     def bf_initialize(self, *args, **kwargs) -> InitializeResult:
#         res = super().bf_initialize(*args, **kwargs)
#         ws = self.workspace
#         self.workspace = ColonyWorkspace(
#             ws.root_uri,
#             self._server.sync_kind,
#             ws.folders.values(),
#         )
#         return res


class ColonyLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'colony'
    # CMD_ADD_TORQUE_PROFILE = 'add_torque_profile'
    CMD_VALIDATE_BLUEPRINT = 'validate_torque_blueprint'
    CMD_START_SANDBOX = 'start_torque_sandbox'

    # def __init__(self):
    #     super().__init__(protocol_cls=ColonyLspProtocol)
    
    # @property
    # def workspace(self) -> ColonyWorkspace:
    #     return cast(ColonyWorkspace, super().workspace)


colony_server = ColonyLanguageServer()


# def _get_file_variables(source):
#     vars = re.findall(r"(\$[\w\.\-]+)", source, re.MULTILINE)
#     return vars  


# def _get_file_inputs(source):
#     yaml_obj = yaml.load(source, Loader=yaml.FullLoader) # todo: refactor
#     inputs_obj = yaml_obj.get('inputs')
#     inputs = []
#     if inputs_obj:
#         for input in inputs_obj:
#             if isinstance(input, str):
#                 inputs.append(f"${input}")
#             elif isinstance(input, dict):
#                 inputs.append(f"${list(input.keys())[0]}")
    
#     return inputs


def _validate(ls, params):
    text_doc = ls.workspace.get_document(params.text_document.uri)
    root = ls.workspace.root_path
    
    source = text_doc.source
    diagnostics = _validate_yaml(source) if source else []

    if not diagnostics: 
        yaml_obj = yaml.load(source, Loader=yaml.FullLoader) # todo: refactor
        doc_type = yaml_obj.get('kind', '')
        doc_lines = text_doc.lines
        

        if doc_type == "blueprint":
            try:
                bp_tree = BlueprintParser(source).parse()
                validator = BlueprintValidationHandler(bp_tree, root)
                diagnostics += validator.validate()
            except Exception as ex:
                import sys
                print('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
                logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
                return
            

        if doc_type == "application":
            app_tree = AppParser(source).parse()
            validator = AppValidationHandler(app_tree, root)
            diagnostics += validator.validate()
            scripts = applications.get_app_scripts(params.text_document.uri)
                
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
            srv_tree = ServiceParser(source).parse()            
            validator = ServiceValidationHandler(srv_tree, root)
            diagnostics += validator.validate()
                
            vars = services.get_service_vars(params.text_document.uri)
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
def did_change(ls, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    if '/blueprints/' in params.text_document.uri or \
       '/applications/' in params.text_document.uri or \
       '/services/' in params.text_document.uri:
        _validate(ls, params)
        text_doc = ls.workspace.get_document(params.text_document.uri)
        root = ls.workspace.root_path
        
        source = text_doc.source
        yaml_obj = yaml.load(source, Loader=yaml.FullLoader) # todo: refactor
        doc_type = yaml_obj.get('kind', '')
        
        if doc_type == "application":
            app_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
            applications.reload_app_details(app_name=app_name, app_source=source)
            
        elif doc_type == "TerraForm":
            srv_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
            services.reload_service_details(srv_name, srv_source=source)


# @colony_server.feature(TEXT_DOCUMENT_DID_CLOSE)
# def did_close(server: ColonyLanguageServer, params: DidCloseTextDocumentParams):
#     """Text document did close notification."""
#     if '/blueprints/' in params.text_document.uri or \
#        '/applications/' in params.text_document.uri or \
#        '/services/' in params.text_document.uri:
#         # server.show_message('Text Document Did Close')
#         pass


@colony_server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(server: ColonyLanguageServer, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    if '/blueprints/' in params.text_document.uri or \
       '/applications/' in params.text_document.uri or \
       '/services/' in params.text_document.uri:
        server.show_message('Detected a Colony file', msg_type=MessageType.Log)
        server.workspace.put_document(params.text_document)
        _validate(server, params)



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


@colony_server.feature(CODE_LENS, CodeLensOptions(resolve_provider=False),)
def code_lens(server: ColonyLanguageServer, params: Optional[CodeLensParams] = None) -> Optional[List[CodeLens]]:
    if '/blueprints/' in params.text_document.uri:
        return [
                    CodeLens(
                        range=Range(
                            start=Position(line=0, character=0),
                            end=Position(line=1, character=1),
                        ),
                        command=Command(
                            title='Validate Blueprint on Server',
                            command=ColonyLanguageServer.CMD_VALIDATE_BLUEPRINT,
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
                            command=ColonyLanguageServer.CMD_START_SANDBOX,
                            arguments=[params.text_document.uri]
                        )
                    ),
                ]
    else:
        return None


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


# @colony_server.feature(TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL, SemanticTokensOptions(
#                 work_done_progress=False,
#                 legend=SemanticTokensLegend(
#                     token_types=['property', 'type', 'class', 'variable'],
#                     token_modifiers=['private', 'static']
#                 ),
#                 range=True,
#                 # full={"delta": False}
#             ))
# def semantic_tokens_range(server: ColonyLanguageServer, params: SemanticTokensParams) -> Optional[Union[SemanticTokens, SemanticTokensPartialResult]]:
#     print('---- TEXT_DOCUMENT_SEMANTIC_TOKENS_RANGE ----')
#     print(locals())
#     # document = server.workspace.get_document(params.text_document.uri)
#     # return Hover(contents="some content", range=Range(
#     #             start=Position(line=31, character=1),
#     #             end=Position(line=31, character=4),
#     #         ))
#     return None


@colony_server.command(ColonyLanguageServer.CMD_START_SANDBOX)
async def start_sandbox(server: ColonyLanguageServer, *args):
    if len(args[0]) == 0:
        server.show_message('Please start the sandbox from the command in the blueprint file.', MessageType.Error)
        return
    
    try:
        config = await server.get_configuration_async(ConfigurationParams(items=[
                ConfigurationItem(
                    scope_uri='',
                    section=ColonyLanguageServer.CONFIGURATION_SECTION)
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
    server.show_message('Starting sandbox from blueprint: ' + blueprint_name)
    try:
        result = subprocess.run([sys.prefix + '/bin/colony', 
                                '--token', token,
                                '--account', account,
                                '--space', space,
                                'sb', 'start', blueprint_name], 
                                cwd=server.workspace.root_path,
                                capture_output=True, text=True)
    except Exception as ex:
        print(ex)
    if result.stderr:
        server.show_message_log(result.stderr, MessageType.Error)
        server.show_message('Error while starting the sandbox. Check the output window for more details.', MessageType.Error)
        return
    print(result.stderr)
    print(result.stdout)
    if result.stderr:
        error_lines = result.stderr.splitlines()
        sep = error_lines[2].split(' ')
        diags = []
        for line in range(3, len(error_lines)):
            msg = error_lines[line][0:len(sep[0])] + ': ' + error_lines[line][len(sep[0])+1: len(error_lines[line])].strip()
            diags.append(Diagnostic(
                range=Range(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=1),
                ),
                message=msg
            ))
        server.publish_diagnostics(args[0][0], diags)
        server.show_message('Validation complete. Check the Problems view for any issues.')
    else:
        server.show_message('Validation completed. Blueprint is valid.')
    server.show_message('Sandbox is ready. See details in the Output view.')
    server.show_message_log('Sandbox ID: ' + 'sandbox-id')
    server.show_message_log('Sandbox URL: ' + 'sandbox-url')
    

@colony_server.command(ColonyLanguageServer.CMD_VALIDATE_BLUEPRINT)
async def validate_blueprint(server: ColonyLanguageServer, *args):
    if len(args[0]) == 0:
        server.show_message('Please validate the blueprint from the command in the blueprint file.', MessageType.Error)
        return
    
    try:
        config = await server.get_configuration_async(ConfigurationParams(items=[
                ConfigurationItem(
                    scope_uri='',
                    section=ColonyLanguageServer.CONFIGURATION_SECTION)
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
    # print(os.getcwd())
    # print(sys.prefix, sys.base_prefix)
    # print(sys.prefix == sys.base_prefix)
    # print(os.getenv('VIRTUAL_ENV'))
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
        server.show_message_log(result.stderr)
        error_lines = result.stderr.splitlines()
        sep = error_lines[2].split(' ')
        diags = []
        for line in range(3, len(error_lines)):
            msg = error_lines[line][0:len(sep[0])] + ': ' + error_lines[line][len(sep[0])+1: len(error_lines[line])].strip()
            diags.append(Diagnostic(
                range=Range(
                    start=Position(line=0, character=0),
                    end=Position(line=0, character=1),
                ),
                message=msg
            ))
        server.publish_diagnostics(args[0][0], diags)
        server.show_message('Validation complete. Check the Problems view for any issues.')
    else:
        server.show_message('Validation completed. Blueprint is valid.')
    
