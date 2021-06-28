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
from pygls.lsp import types
from pygls.lsp.types.basic_structures import DiagnosticSeverity, VersionedTextDocumentIdentifier
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

from server.ats.parser import BlueprintParser, BlueprintTree

from server.utils import services, applications, common
from pygls.protocol import LanguageServerProtocol

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
from pygls.workspace import Document, Workspace, position_from_utf16

DEBOUNCE_DELAY = 0.3


COUNT_DOWN_START_IN_SECONDS = 10
COUNT_DOWN_SLEEP_IN_SECONDS = 1

APPLICATIONS = {}
SERVICES = {}

PREDEFINED_COLONY_INPUTS = [
    "$colony.environment.id",
    "$colony.environment.virtual_network_id",
    "$colony.environment.public_address"
    "$colony.repos.branch.current"
]

class BlueprintValidationHandler:
    # TODO: reffactor to have a single validate function 
    def __init__(self, tree: BlueprintTree):
        self._tree = tree
        self._diagnostics = []

    def _validate_dependency_exists(self):
        message = "The app '{}' is not part of the blueprint applications section"
        apps = [app.name for app in self._tree.apps_node.apps]

        for app in self._tree.apps_node.apps:
            for name, node in app.depends_on.items():
                if name not in apps:
                    self._diagnostics.append(Diagnostic(
                        range=Range(
                            start=Position(line=node.start[0], character=node.start[1]),
                            end=Position(line=node.end[0], character=node.end[1]),
                        ),
                        message=message.format(name)
                    ))
    
    def validate_non_existing_app_is_declared(self, root_path: str):
        message = "The app '{}' could not be found in the /applications folder"
        
        diagnostics: List[Diagnostic] = []

        for app in self._tree.apps_node.apps:
            app_path = os.path.join(root_path, "applications", app.name, "{}.yaml".format(app.name))

            if not os.path.isfile(app_path):
                diagnostics.append(Diagnostic(
                    range=Range(
                        start=Position(line=app.start[0], character=app.start[1]),
                        end=Position(line=app.start[0], character=app.start[1] + len(app.name)),
                    ),
                    message=message.format(app.name)
                ))
        
        return diagnostics

    def _check_for_unused_bluerprint_inputs(self): 
        
        used_vars = set()
        for app in self._tree.apps_node.apps:
            used_vars.update({var.value.replace("$", "") for var in app.inputs_node.inputs})

        message = "Unused variable {}"

        for input in self._tree.inputs_node.inputs:
            if input.name not in used_vars:
                self._diagnostics.append(Diagnostic(
                    range=Range(
                        start=Position(line=input.start[0], character=input.start[1]),
                        end=Position(line=input.start[0], character=input.start[1] + len(input.name))
                    ),
                    message=message.format(input.name),
                    severity=DiagnosticSeverity.Warning
                ))

    def _validate_var_being_used_is_defined(self):
        bp_inputs = {input.name for input in self._tree.inputs_node.inputs}
        message = "Variable '{}' is not defined"
        for app in self._tree.apps_node.apps:
            for input in app.inputs_node.inputs:
                # we need to check values starting with '$' 
                # and they shouldnt be colony related
                if input.value.startswith("$") and "." not in input.value:
                    var = input.value.replace("$", "")
                    if var not in bp_inputs:
                        self._diagnostics.append(Diagnostic(
                            range=Range(
                                start=Position(line=input.start[0], character=input.start[1]),
                                end=Position(line=input.end[0], character=input.end[1])
                            ),
                            message=message.format(input.value)
                        ))

    def validate(self):
        # warnings
        self._check_for_unused_bluerprint_inputs()
        # errors
        self._validate_dependency_exists()
        self._validate_var_being_used_is_defined()
        return self._diagnostics

    # # TODO: must work with tree
    # def _get_used_vars(self, yaml_doc: dict) -> set:

    #     used_vars = set()

    #     for app in yaml_doc.get('applications', []):
    #         app_name = list(app.keys()).pop()
    #         inputs = app[app_name].get("input_values", [])

    #         for items in inputs:
    #             used_vars.add(list(items.values()).pop().replace("$", ""))

    #     return used_vars

class ColonyWorkspace(Workspace):
    """
    Add colony-specific properties
    """

    def __init__(self, root_uri, sync_kind, workspace_folders):
        self._colony_objs = {}

        super().__init__(root_uri, sync_kind=sync_kind, workspace_folders=workspace_folders)

    @property
    def colony_objs(self):
        return self._colony_objs

    def _update_document(self, text_document: Union[types.TextDocumentItem, types.VersionedTextDocumentIdentifier]) -> None:
        self.logger.debug("updating document '%s'", text_document.uri)
        uri = text_document.uri
        colony_obj = yaml.load(self.get_document(uri).source, Loader=yaml.FullLoader)
        self._colony_objs[uri] = colony_obj

    def update_document(self, text_doc: VersionedTextDocumentIdentifier, change: workspace.TextDocumentContentChangeEvent):
        super().update_document(text_doc, change)
        self._update_document(text_doc)

    def put_document(self, text_document: types.TextDocumentItem) -> None:
        super().put_document(text_document)
        self._update_document(text_document)


class ColonyLspProtocol(LanguageServerProtocol):
    """Custom protocol that replaces the workspace with a ColonyWorkspace
    instance.
    """

    workspace: ColonyWorkspace

    def bf_initialize(self, *args, **kwargs) -> InitializeResult:
        res = super().bf_initialize(*args, **kwargs)
        ws = self.workspace
        self.workspace = ColonyWorkspace(
            ws.root_uri,
            self._server.sync_kind,
            ws.folders.values(),
        )
        return res


class ColonyLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'colonyServer'

    # def __init__(self):
    #     super().__init__(protocol_cls=ColonyLspProtocol)
    
    # @property
    # def workspace(self) -> ColonyWorkspace:
    #     return cast(ColonyWorkspace, super().workspace)


colony_server = ColonyLanguageServer()


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
                    # d = Diagnostic(
                    #     range=Range(
                    #         start=Position(line=i, character=col_pos),
                    #         end=Position(line=i, character=col_pos + 1 +len(var))
                    #     ),
                    #     message=msg
                    # )
                    # diagnostics.append(d)

        if doc_type == "blueprint":
            bp_tree = BlueprintParser(source).parse()
            validator = BlueprintValidationHandler(bp_tree)

            diagnostics += validator.validate()
            diagnostics += validator.validate_non_existing_app_is_declared(root)

            # print(ls.workspace.colony_objs)
            # apps = applications.get_available_applications(root, APPLICATIONS)
            # for app in yaml_obj.get('applications', []):
            #     app = list(app.keys())[0]
            #     if app not in apps.keys():
            #         for i in range(len(doc_lines)):
            #             col_pos = doc_lines[i].find(app)
            #             if col_pos == -1:
            #                 continue
            #             d = Diagnostic(
            #                 range=Range(
            #                     start=Position(line=i, character=col_pos),
            #                     end=Position(line=i, character=col_pos + 1 +len(app))
            #                 ),
            #                 message=f"Application '{app}' doesn't exist"
            #             )
            #             diagnostics.append(d)
            srvs = services.get_available_services(root, SERVICES)
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
            applications.load_app_details(app_name, params.text_document.uri, APPLICATIONS)
    elif doc_type == "TerraForm":
        srv_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
        if SERVICES and srv_name not in SERVICES: # if there is already a cache, add this file
            services.load_service_details(srv_name, params.text_document.uri, SERVICES)


@colony_server.feature(TEXT_DOCUMENT_DID_CLOSE)
def did_close(server: ColonyLanguageServer, params: DidCloseTextDocumentParams):
    """Text document did close notification."""
    server.show_message('Text Document Did Close')


@colony_server.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(ls, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    ls.show_message('Text Document Did Open')
    ls.workspace.put_document(params.text_document)
    _validate(ls, params)
