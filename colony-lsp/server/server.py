import asyncio
from dataclasses import dataclass
import logging
import subprocess
import sys
import textwrap
import tabulate
        
from server.ats.trees.common import BaseTree
from server.validation.factory import ValidatorFactory

from pygls.lsp.types.language_features.completion import InsertTextMode

# from pygls.lsp.types.language_features.semantic_tokens import SemanticTokens, SemanticTokensEdit, SemanticTokensLegend, SemanticTokensOptions, SemanticTokensParams, SemanticTokensPartialResult, SemanticTokensRangeParams
from pygls.lsp import types
from pygls.lsp.types.basic_structures import TextEdit, VersionedTextDocumentIdentifier
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
                               TEXT_DOCUMENT_SEMANTIC_TOKENS, TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL, TEXT_DOCUMENT_SEMANTIC_TOKENS_FULL_DELTA)
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



class ColonyLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = 'colony'
    CMD_VALIDATE_BLUEPRINT = 'validate_torque_blueprint'
    CMD_START_SANDBOX = 'start_torque_sandbox'


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

    try:
        tree = Parser(source).parse()
        diagnostics += _diagnose_tree_errors(tree)
        cls_validator = ValidatorFactory.get_validator(tree)
        validator = cls_validator(tree, text_doc)
        diagnostics += validator.validate()
    except ParserError as e:
        diagnostics.append(
            Diagnostic(
                range = Range(
                    start=Position(line=e.start_pos[0], character=e.start_pos[1]),
                    end=Position(line=e.end_pos[0], character=e.end_pos[1])),
                message=e.message))
    except ValueError as e:
        diagnostics.append(
            Diagnostic(
                range = Range(
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
def did_change(ls, params: DidChangeTextDocumentParams):
    """Text document did change notification."""
    if '/blueprints/' in params.text_document.uri or \
       '/applications/' in params.text_document.uri or \
       '/services/' in params.text_document.uri:
        _validate(ls, params)
        text_doc = ls.workspace.get_document(params.text_document.uri)
        
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
    
#     return None



@colony_server.feature(COMPLETION, CompletionOptions(resolve_provider=False, trigger_characters=['.']))
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
    
        
    fdrs = colony_server.workspace.folders
    root = colony_server.workspace.root_path
    
    if doc_type == "blueprint":
        items=[]
        if params.context.trigger_character == '.':
            words = common.preceding_words(doc, params.position)
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
                    bp_tree = Parser(doc.source).parse()
                                        
                    options = []
                    if cur_word.startswith('colony'):
                        if cur_word == 'colony.':
                            options = ['environment', 'repos']
                            if bp_tree.applications and len(bp_tree.applications.nodes) > 0:
                                options.append('applications')
                            if bp_tree.services and len(bp_tree.services.nodes) > 0:
                                options.append('services')
                        elif cur_word == 'colony.environment.':
                            options = ['id', 'virtual_network_id', 'public_address']
                        elif cur_word == 'colony.repos.':
                            options = ['branch']
                        elif cur_word == 'colony.repos.branch.':
                            options = ['current']
                        elif cur_word == 'colony.applications.':
                            if bp_tree.applications and len(bp_tree.applications.nodes) > 0:
                                for app in bp_tree.applications.nodes:
                                    options.append(app.id.text)
                        elif cur_word == 'colony.services.':
                            if bp_tree.services and len(bp_tree.services.nodes) > 0:
                                for srv in bp_tree.services.nodes:
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
                        items.append(CompletionItem(label=option,
                                                    kind=CompletionItemKind.Property,
                                                    text_edit=TextEdit(
                                                        range=Range(start=Position(line=line, character=char),
                                                                    end=Position(line=line, character=char+len(option))),
                                                                    new_text=option
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
            
            # if parent == "input_values":
            #     available_inputs = _get_file_inputs(doc.source)
            #     inputs = [CompletionItem(label=option, kind=CompletionItemKind.Variable) for option in available_inputs]
            #     items.extend(inputs)
            #     inputs = [CompletionItem(label=option, kind=CompletionItemKind.Variable) for option in PREDEFINED_COLONY_INPUTS]
            #     items.extend(inputs)
            #     # TODO: add output generated variables of apps/services in this blueprint ($colony.applications.app_name.outputs.output_name, $colony.services.service_name.outputs.output_name)
        
        return CompletionList(
            is_incomplete=(len(items)==0),
            items=items
        )
    elif doc_type == "application":
        words = common.preceding_words(doc, params.position)
        if words and len(words) == 1:
            if words[0] == "script:":
                scripts = applications.get_app_scripts(params.text_document.uri)
                return CompletionList(
                    is_incomplete=False,
                    items=[CompletionItem(label=script,
                                          kind=CompletionItemKind.File) for script in scripts],
                )
            # TODO: check based on allow_variable
            # elif words[0] in ["vm_size:", "instance_type:", "pull_secret:", "port:", "port-range:"]:
            #     available_inputs = _get_file_inputs(doc.source)
            #     return CompletionList(
            #         is_incomplete=False,
            #         items=[CompletionItem(label=option, kind=CompletionItemKind.Variable) for option in available_inputs],
            #     )

    if doc_type == "TerraForm":
        words = common.preceding_words(doc, params.position)
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
            # TODO: check based on allow_variable
            # elif words[0] in ["vm_size:", "instance_type:", "pull_secret:", "port:", "port-range:"]:
            #     available_inputs = _get_file_inputs(doc.source)
            #     return CompletionList(
            #         is_incomplete=False,
            #         items=[CompletionItem(label=option, kind=CompletionItemKind.Variable) for option in available_inputs],
            #     )

    else:
        return CompletionList(is_incomplete=True, items=[])


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
                            title='Validate on Server',
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
        
        if bp_tree.applications:
            for app in bp_tree.applications.nodes:
                target_path = os.path.join(root, "applications", app.id.text, app.id.text+".yaml")
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    tooltip = "Open the application file at " + target_path
                    links.append(DocumentLink(range=Range(
                                              start=Position(line=app.id.start_pos[0], character=app.id.start_pos[1]),
                                              end=Position(line=app.id.start_pos[0], character=app.start_pos[1]+len(app.id.text))), 
                                              target=pathlib.Path(target_path).as_uri(), 
                                              tooltip=tooltip))
        
        if bp_tree.services:
            for srv in bp_tree.services.nodes:
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
            app_tree = Parser(doc.source).parse()        
            app_name = doc.filename.replace('.yaml', '')    
        except Exception as ex:
            import sys
            logging.error('Error on line {}'.format(sys.exc_info()[-1].tb_lineno), type(ex).__name__, ex)
            return links
        
        if app_tree.configuration:
            if app_tree.configuration.healthcheck:
                if app_tree.configuration.healthcheck.script:
                    script = app_tree.configuration.healthcheck.script
                    file_name = script.text
                    target_path = os.path.join(root, "applications", app_name, file_name)
                    if os.path.exists(target_path) and os.path.isfile(target_path):
                        tooltip = "Open the script file at " + target_path
                        links.append(DocumentLink(range=Range(
                                                  start=Position(line=script.start_pos[0], character=script.start_pos[1]),
                                                  end=Position(line=script.start_pos[0], character=script.start_pos[1]+len(script.text))), 
                                                  target=pathlib.Path(target_path).as_uri(), 
                                                  tooltip=tooltip))
            
            if app_tree.configuration.initialization:
                if app_tree.configuration.initialization.script:
                    script = app_tree.configuration.initialization.script
                    file_name = script.text
                    target_path = os.path.join(root, "applications", app_name, file_name)
                    if os.path.exists(target_path) and os.path.isfile(target_path):
                        tooltip = "Open the script file at " + target_path
                        links.append(DocumentLink(range=Range(
                                                  start=Position(line=script.start_pos[0], character=script.start_pos[1]),
                                                  end=Position(line=script.start_pos[0], character=script.start_pos[1]+len(script.text))), 
                                                  target=pathlib.Path(target_path).as_uri(), 
                                                  tooltip=tooltip))
            
            if app_tree.configuration.start:
                if app_tree.configuration.start.script:
                    script = app_tree.configuration.start.script
                    file_name = script.text
                    target_path = os.path.join(root, "applications", app_name, file_name)
                    if os.path.exists(target_path) and os.path.isfile(target_path):
                        tooltip = "Open the script file at " + target_path
                        links.append(DocumentLink(range=Range(
                                                  start=Position(line=script.start_pos[0], character=script.start_pos[1]),
                                                  end=Position(line=script.start_pos[0], character=script.start_pos[1]+len(script.text))), 
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
            if srv_tree.variables.var_file:
                script = srv_tree.variables.var_file
                file_name = script.text
                target_path = os.path.join(root, "services", srv_name, file_name)
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    tooltip = "Open the variables file at " + target_path
                    links.append(DocumentLink(range=Range(
                                              start=Position(line=script.start_pos[0], character=script.start_pos[1]),
                                              end=Position(line=script.start_pos[0], character=script.start_pos[1]+len(script.text))), 
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
        process = subprocess.Popen([sys.prefix + '/bin/colony', 
                                    '--token', token,
                                    '--account', account,
                                    '--space', space,
                                    'sb', 'start', blueprint_name, '-d', '30'], 
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
            cols = line.split('  ')
            table.append(['\n'.join(textwrap.wrap(cols[0], width=30)), 
                          '\n'.join(textwrap.wrap(cols[1], width=60))])
        
        server.show_message_log(tabulate.tabulate(table, headers, tablefmt="simple"))        
        server.show_message('Validation complete. Check the Problems view for any issues.')
    else:
        server.show_message('Validation completed. Blueprint is valid.')
    
