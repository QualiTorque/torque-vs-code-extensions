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
import logging
import os
import pathlib
import shlex
import subprocess
import sys
import textwrap
from json import JSONDecodeError
from typing import List, Optional
from urllib.parse import unquote

import tabulate
import yaml
from pygls.lsp.methods import (
    CODE_LENS,
    COMPLETION,
    DOCUMENT_LINK,
    TEXT_DOCUMENT_DID_CHANGE,
    TEXT_DOCUMENT_DID_OPEN,
    WORKSPACE_DID_CHANGE_WATCHED_FILES,
)
from pygls.lsp.types import (
    CodeLens,
    CodeLensOptions,
    CodeLensParams,
    Command,
    CompletionItem,
    CompletionItemKind,
    CompletionList,
    CompletionOptions,
    CompletionParams,
    ConfigurationItem,
    ConfigurationParams,
    Diagnostic,
    DidChangeTextDocumentParams,
    DidChangeWorkspaceFoldersParams,
    DidOpenTextDocumentParams,
    DocumentLink,
    DocumentLinkParams,
    MessageType,
    Position,
    Range,
    workspace,
)
from pygls.lsp.types.basic_structures import TextEdit
from pygls.server import LanguageServer
from server.ats.parser import Parser, ParserError
from server.ats.trees.app import AppTree
from server.ats.trees.common import BaseTree, PropertyNode
from server.completers.resolver import CompletionResolver
from server.constants import AWS_REGIONS, AZURE_REGIONS
from server.utils import common
from server.utils.applications import ApplicationsManager as applications
from server.utils.common import get_repo_root_path, is_var_allowed
from server.utils.services import ServicesManager as services
from server.validation.factory import ValidatorFactory

DEBOUNCE_DELAY = 0.3


class TorqueLanguageServer(LanguageServer):
    CONFIGURATION_SECTION = "torque"
    CMD_VALIDATE_BLUEPRINT = "validate_torque_blueprint"
    CMD_START_SANDBOX = "start_torque_sandbox"
    CMD_LIST_TORQUE_PROFILES = "list_torque_profiles"
    CMD_TORQUE_LOGIN = "torque_login"
    CMD_REMOVE_PROFILE = "remove_profile"
    CMD_LIST_SANDBOXES = "list_sandboxes"
    CMD_LIST_BLUEPRINTS = "list_blueprints"
    CMD_GET_SANDBOX = "get_sandbox"
    CMD_END_SANDBOX = "end_sandbox"
    latest_opened_document = None


torque_ls = TorqueLanguageServer()


def _is_torque_file(file_uri):
    return (
        "/blueprints/" in file_uri
        or "/applications/" in file_uri
        or "/services/" in file_uri
    )


def _diagnose_tree_errors(tree: BaseTree) -> list:
    diagnostics = []
    for error in tree.errors:
        d = Diagnostic(
            range=Range(
                start=Position(line=error.start_pos[0], character=error.start_pos[1]),
                end=Position(line=error.end_pos[0], character=error.end_pos[1]),
            ),
            message=error.message,
        )
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
                        end=Position(line=e.end_pos[0], character=e.end_pos[1]),
                    ),
                    message=e.message,
                )
            )
        except ValueError as e:
            diagnostics.append(
                Diagnostic(
                    range=Range(
                        start=Position(line=0, character=0),
                        end=Position(line=0, character=0),
                    ),
                    message=str(e),
                )
            )
        except Exception as ex:
            import sys

            print(
                "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
                type(ex).__name__,
                ex,
            )
            logging.error(
                "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
                type(ex).__name__,
                ex,
            )

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
                end=Position(line=mark.line - 1, character=mark.column),
            ),
            message=ex.problem,
            source=type(torque_ls).__name__,
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
        yaml_obj = yaml.load(source, Loader=yaml.FullLoader)  # todo: refactor
        doc_type = yaml_obj.get("kind", "")

        if doc_type == "application":
            app_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
            applications.reload_resource_details(
                resource_name=app_name, resource_source=source
            )

        elif doc_type == "TerraForm":
            srv_name = pathlib.Path(params.text_document.uri).name.replace(".yaml", "")
            services.reload_resource_details(
                resource_name=srv_name, resource_source=source
            )


@torque_ls.feature(TEXT_DOCUMENT_DID_OPEN)
async def did_open(server: TorqueLanguageServer, params: DidOpenTextDocumentParams):
    """Text document did open notification."""
    if _is_torque_file(params.text_document.uri):
        server.latest_opened_document = params.text_document
        server.show_message("Detected a Torque file", msg_type=MessageType.Log)
        server.workspace.put_document(params.text_document)
        _validate(server, params)


@torque_ls.feature(WORKSPACE_DID_CHANGE_WATCHED_FILES)
async def workspace_changed(
    server: TorqueLanguageServer, params: DidChangeWorkspaceFoldersParams
):
    """Workspace changed notification."""
    current_file_changed = False
    for change in params.changes:
        if change.uri != server.latest_opened_document.uri:
            if "/applications/" in change.uri or "/services/" in change.uri:
                if change.type != workspace.FileChangeType.Deleted:
                    text_doc = server.workspace.get_document(change.uri)
                    source = text_doc.source
                    yaml_obj = yaml.load(
                        source, Loader=yaml.FullLoader
                    )  # todo: refactor
                    doc_type = yaml_obj.get("kind", "")

                    if doc_type == "application":
                        app_name = pathlib.Path(change.uri).name.replace(".yaml", "")
                        applications.reload_resource_details(
                            resource_name=app_name, resource_source=source
                        )

                    elif doc_type == "TerraForm":
                        srv_name = pathlib.Path(change.uri).name.replace(".yaml", "")
                        services.reload_resource_details(
                            resource_name=srv_name, resource_source=source
                        )
                else:
                    if "/applications/" in change.uri:
                        app_name = pathlib.Path(change.uri).name.replace(".yaml", "")
                        applications.remove_resource_details(resource_name=app_name)

                    elif "/services/" in change.uri:
                        srv_name = pathlib.Path(change.uri).name.replace(".yaml", "")
                        services.remove_resource_details(resource_name=srv_name)
        else:
            current_file_changed = True
    try:
        if (
            "/blueprints/" in server.latest_opened_document.uri
            and not current_file_changed
        ):
            print("validating")
            _validate(
                server,
                DidOpenTextDocumentParams(text_document=server.latest_opened_document),
            )
    except Exception as ex:
        logging.error(ex)


@torque_ls.feature(COMPLETION, CompletionOptions(resolve_provider=False))
def completions(
    server: TorqueLanguageServer, params: Optional[CompletionParams] = None
) -> CompletionList:
    """Returns completion items."""
    if not _is_torque_file(params.text_document.uri):
        return CompletionList(is_incomplete=True, items=[])

    doc = server.workspace.get_document(params.text_document.uri)

    try:
        yaml_obj = yaml.load(doc.source, Loader=yaml.FullLoader)
        if yaml_obj:
            doc_type = yaml_obj.get("kind", "")
        else:
            return CompletionList(is_incomplete=True, items=[])
    except yaml.MarkedYAMLError:
        return CompletionList(is_incomplete=True, items=[])

    try:
        tree = Parser(doc.source).parse()
    except Exception as ex:
        import sys

        logging.error(
            "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
            type(ex).__name__,
            ex,
        )
        return CompletionList(is_incomplete=True, items=[])

    words = common.preceding_words(doc, params.position)
    last_word = words[-1] if words else ""

    if last_word.endswith("$") or last_word.endswith(":"):
        if is_var_allowed(tree, params.position):
            inputs_names_list = [i_node.key.text for i_node in tree.get_inputs()]
            if doc_type == "blueprint":
                inputs_names_list.append("torque")

            line = params.position.line
            char = params.position.character
            suggested_vars = [
                CompletionItem(
                    label=f"${var}",
                    kind=CompletionItemKind.Variable,
                    text_edit=TextEdit(
                        range=Range(
                            start=Position(
                                line=line,
                                character=char - (1 if last_word.endswith("$") else 0),
                            ),
                            end=Position(line=line, character=char),
                        ),
                        new_text=f"${var}"
                        if last_word == "$" or last_word.endswith(":")
                        else f"${{{var}}}",
                    ),
                )
                for var in inputs_names_list
            ]

            return CompletionList(
                is_incomplete=(len(suggested_vars) == 0), items=suggested_vars
            )

    root = get_repo_root_path(doc.path)

    if doc_type == "blueprint":
        parent_node = common.get_parent_node_text(tree, params.position)
        if parent_node == "clouds":
            items = []
            items += [
                CompletionItem(
                    label=script, detail="AWS region", kind=CompletionItemKind.File
                )
                for script in AWS_REGIONS
            ]

            items += [
                CompletionItem(
                    label=script, detail="Azure region", kind=CompletionItemKind.File
                )
                for script in AZURE_REGIONS
            ]

            return CompletionList(
                is_incomplete=False,
                items=items,
            )

        items = []
        if last_word.endswith("."):
            if words and len(words) > 1 and words[1] == words[-1] and words[0] != "-":
                cur_word = words[-1]
                word_parts = cur_word.split("$")
                if word_parts:
                    if word_parts[-1].startswith("{torque."):
                        cur_word = word_parts[-1][1:]
                    elif word_parts[-1].startswith("torque."):
                        cur_word = word_parts[-1]
                    else:
                        cur_word = ""
                if cur_word:
                    options = []
                    if cur_word.startswith("torque"):
                        if cur_word == "torque.":
                            options = ["environment", "repos"]
                            if tree.applications and len(tree.applications.nodes) > 0:
                                options.append("applications")
                            if tree.services and len(tree.services.nodes) > 0:
                                options.append("services")
                        elif cur_word == "torque.environment.":
                            options = ["id", "virtual_network_id", "public_address"]
                        elif cur_word == "torque.repos.":
                            options = ["current"]
                        elif cur_word == "torque.repos.current.":
                            options = ["branch"]
                        elif cur_word.startswith("torque.repos."):
                            parts = cur_word.split(".")
                            if len(parts) == 4 and parts[2] != "":
                                options = ["token", "url"]
                        elif cur_word == "torque.applications.":
                            for app in tree.get_applications():
                                options.append(app.id.text)
                        elif cur_word == "torque.services.":
                            for srv in tree.get_services():
                                options.append(srv.id.text)
                        elif cur_word.startswith("torque.applications."):
                            parts = cur_word.split(".")
                            if len(parts) == 4 and parts[2] != "":
                                options = ["outputs", "dns"]
                            elif len(parts) == 5 and parts[3] == "outputs":
                                apps = applications.get_available_resources(root)
                                for app in apps:
                                    if app == parts[2]:
                                        outputs = applications.get_outputs(
                                            resource_name=parts[2]
                                        )
                                        if outputs:
                                            options.extend(outputs)
                                        break
                        elif cur_word.startswith("torque.services."):
                            parts = cur_word.split(".")
                            if len(parts) == 4 and parts[2] != "":
                                options.append("outputs")
                            elif len(parts) == 5 and parts[3] == "outputs":
                                apps = services.get_available_resources(root)
                                for app in apps:
                                    if app == parts[2]:
                                        outputs = services.get_outputs(
                                            resource_name=parts[2]
                                        )
                                        if outputs:
                                            options.extend(outputs)
                                        break

                    line = params.position.line
                    char = params.position.character
                    for option in options:
                        if option in [
                            "applications",
                            "services",
                            "environment",
                            "repos",
                            "current",
                            "outputs",
                        ]:
                            command = Command(
                                command="editor.action.triggerSuggest", title=option
                            )
                        else:
                            command = None
                        items.append(
                            CompletionItem(
                                label=option,
                                command=command,
                                kind=CompletionItemKind.Property,
                                text_edit=TextEdit(
                                    range=Range(
                                        start=Position(line=line, character=char),
                                        end=Position(
                                            line=line, character=char + len(option)
                                        ),
                                    ),
                                    new_text=option + ("." if command else ""),
                                ),
                            )
                        )

        else:
            try:
                path = common.get_path_to_pos(tree, params.position)
                completer = CompletionResolver.get_completer(path)
                completions = completer(
                    server.workspace, params, tree
                ).get_completions()
                items += completions
            except ValueError:
                logging.error("Unable to build a completions list")

        if items:
            return CompletionList(is_incomplete=False, items=items)
        else:
            return CompletionList(is_incomplete=True, items=[])

    elif doc_type == "application":
        if words and len(words) == 1:
            if words[0] == "script:":
                scripts = applications.get_app_scripts(params.text_document.uri)
                return CompletionList(
                    is_incomplete=False,
                    items=[
                        CompletionItem(label=script, kind=CompletionItemKind.File)
                        for script in scripts
                    ],
                )

    elif doc_type == "TerraForm":
        if words and len(words) == 1:
            if words[0] == "var_file:":
                var_files = services.get_service_vars(params.text_document.uri)
                return CompletionList(
                    is_incomplete=False,
                    items=[
                        CompletionItem(
                            label=var["file"],
                            insert_text=f"{var['file']}\r\nvalues:\r\n"
                            + "\r\n".join(
                                [f"  - {var_name}: " for var_name in var["variables"]]
                            ),
                        )
                        for var in var_files
                    ],
                    kind=CompletionItemKind.File,
                )

    else:
        line = params.position.line
        char = params.position.character
        return CompletionList(
            is_incomplete=False,
            items=[
                CompletionItem(
                    label="No suggestions.",
                    kind=CompletionItemKind.Text,
                    text_edit=TextEdit(
                        new_text="",
                        range=Range(
                            start=Position(
                                line=line,
                                character=char - (1 if last_word.endswith("$") else 0),
                            ),
                            end=Position(line=line, character=char),
                        ),
                    ),
                )
            ],
        )


@torque_ls.feature(
    CODE_LENS,
    CodeLensOptions(resolve_provider=False),
)
def code_lens(
    server: TorqueLanguageServer, params: Optional[CodeLensParams] = None
) -> Optional[List[CodeLens]]:
    if "/blueprints/" in params.text_document.uri:
        doc = server.workspace.get_document(params.text_document.uri)
        try:
            bp_tree = Parser(doc.source).parse()
        except Exception as ex:
            import sys

            logging.error(
                "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
                type(ex).__name__,
                ex,
            )
            return None

        def to_bool(val: str):
            return val.lower() == "true"

        inputs = []
        bp_inputs = bp_tree.get_inputs()
        for inp in bp_inputs:
            props = inp.value
            item = {}
            item["name"] = inp.key.text
            item["default_value"] = (
                inp.default_value.text if (props and inp.default_value) else ""
            )

            item["optional"] = (
                to_bool(props.optional.text)
                if (props and hasattr(props, "optional") and props.optional)
                else False
            )

            item["display_style"] = (
                props.display_style.text
                if (props and hasattr(props, "display_style") and props.display_style)
                else "text"
            )
            inputs.append(item)
        artifacts = {}
        bp_arts = bp_tree.get_artifacts()
        for art in bp_arts:
            artifacts[art.key.text] = art.value.text if art.value else ""

        return [
            CodeLens(
                range=Range(
                    start=Position(line=0, character=0),
                    end=Position(line=1, character=1),
                ),
                command=Command(
                    title="Validate with Torque",
                    command=TorqueLanguageServer.CMD_VALIDATE_BLUEPRINT,
                    arguments=[params.text_document.uri],
                ),
            ),
            CodeLens(
                range=Range(
                    start=Position(line=0, character=0),
                    end=Position(line=1, character=1),
                ),
                command=Command(
                    title="Start Sandbox",
                    command="extension.openReserveForm",
                    arguments=[params.text_document.uri, inputs, artifacts, ""],
                ),
            ),
        ]
    else:
        return None


@torque_ls.feature(DOCUMENT_LINK)
async def lsp_document_link(
    server: TorqueLanguageServer,
    params: DocumentLinkParams,
) -> List[DocumentLink]:
    links: List[DocumentLink] = []
    if not _is_torque_file(params.text_document.uri):
        return links

    await asyncio.sleep(DEBOUNCE_DELAY)

    doc = server.workspace.get_document(params.text_document.uri)
    try:
        yaml_obj = yaml.load(doc.source, Loader=yaml.FullLoader)
        if yaml_obj:
            doc_type = yaml_obj.get("kind", "")
        else:
            return links
    except yaml.MarkedYAMLError:
        return links

    root = get_repo_root_path(doc.path)

    if doc_type == "blueprint":
        try:
            bp_tree = Parser(doc.source).parse()
        except Exception as ex:
            import sys

            logging.error(
                "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
                type(ex).__name__,
                ex,
            )
            return links

        resources = {
            "service": bp_tree.get_services,
            "application": bp_tree.get_applications,
        }

        for res_type, func in resources.items():
            for res in func():
                target_path = os.path.join(
                    root, f"{res_type}s", res.id.text, res.id.text + ".yaml"
                )
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    tooltip = f"Open the {res_type} file at " + target_path
                    links.append(
                        DocumentLink(
                            range=Range(
                                start=Position(
                                    line=res.id.start_pos[0],
                                    character=res.id.start_pos[1],
                                ),
                                end=Position(
                                    line=res.id.start_pos[0],
                                    character=res.start_pos[1] + len(res.id.text),
                                ),
                            ),
                            target=pathlib.Path(target_path).as_uri(),
                            tooltip=tooltip,
                        )
                    )

    elif doc_type == "application":
        try:
            app_tree: AppTree = Parser(doc.source).parse()
            app_name = doc.filename.replace(".yaml", "")
        except Exception as ex:
            import sys

            logging.error(
                "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
                type(ex).__name__,
                ex,
            )
            return links

        if app_tree.configuration:
            for state in ["healthcheck", "initialization", "start"]:
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
                    links.append(
                        DocumentLink(
                            range=Range(
                                start=Position(
                                    line=script.value.start_pos[0],
                                    character=script.value.start_pos[1],
                                ),
                                end=Position(
                                    line=script.value.start_pos[0],
                                    character=script.value.start_pos[1]
                                    + len(script.text),
                                ),
                            ),
                            target=pathlib.Path(target_path).as_uri(),
                            tooltip=tooltip,
                        )
                    )

    elif doc_type == "TerraForm":
        try:
            srv_tree = Parser(doc.source).parse()
            srv_name = doc.filename.replace(".yaml", "")
        except Exception as ex:
            import sys

            logging.error(
                "Error on line {}".format(sys.exc_info()[-1].tb_lineno),
                type(ex).__name__,
                ex,
            )
            return links

        if srv_tree.variables:
            script: PropertyNode = srv_tree.variables.var_file
            if script and script.value:
                file_name = script.text
                target_path = os.path.join(root, "services", srv_name, file_name)
                if os.path.exists(target_path) and os.path.isfile(target_path):
                    tooltip = "Open the variables file at " + target_path
                    links.append(
                        DocumentLink(
                            range=Range(
                                start=Position(
                                    line=script.value.start_pos[0],
                                    character=script.value.start_pos[1],
                                ),
                                end=Position(
                                    line=script.value.start_pos[0],
                                    character=script.value.start_pos[1]
                                    + len(script.text),
                                ),
                            ),
                            target=pathlib.Path(target_path).as_uri(),
                            tooltip=tooltip,
                        )
                    )

    return links


def _run_torque_cli_command(command: str, **kwargs):
    cmd_list = [sys.executable, "-m"] + shlex.split(command)

    res = subprocess.run(
        cmd_list,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        **kwargs,
    )

    return res.stdout, res.stderr


async def _get_profile(server: TorqueLanguageServer):
    try:
        config = await server.get_configuration_async(
            ConfigurationParams(
                items=[
                    ConfigurationItem(
                        scope_uri="", section=TorqueLanguageServer.CONFIGURATION_SECTION
                    )
                ]
            )
        )
        active_profile = config[0].get("activeProfile")
    except Exception:
        active_profile = ""

    return active_profile


@torque_ls.command(TorqueLanguageServer.CMD_START_SANDBOX)
async def start_sandbox(server: TorqueLanguageServer, *args):
    if len(args[0]) == 0:
        server.show_message(
            "Please start the sandbox from the command in the blueprint file.",
            MessageType.Error,
        )
        return

    active_profile = await _get_profile(server)

    if not active_profile:
        server.show_message(
            "Please have at least one profile set as the default one.",
            MessageType.Error,
        )
        return

    blueprint_name = args[0][0]

    if blueprint_name.endswith(".yaml"):
        dev_mode = True
        blueprint_name = unquote(pathlib.Path(args[0][0]).name.replace(".yaml", ""))
    else:
        dev_mode = False

    sandbox_name = args[0][1]
    duration = args[0][2]
    inputs_args = args[0][3]
    artifacts_args = args[0][4]

    server.show_message("Starting sandbox from blueprint: " + blueprint_name)
    server.show_message_log("Starting sandbox from blueprint: " + blueprint_name)
    if dev_mode:
        server.show_message_log(
            "If there are local changes it might take some more time to get ready."
        )

    try:
        command = f'torque --profile {active_profile} sb start "{blueprint_name}" -d {duration}'

        if inputs_args:
            command += f' -i "{inputs_args}"'
        if artifacts_args:
            command += f' -a "{artifacts_args}"'
        if sandbox_name:
            command += f' -n "{sandbox_name}"'
        if not dev_mode:
            branch = args[0][5]
            command += f" -t 0 -b {branch}"

        cwd = server.workspace.root_path if dev_mode else None
        stdout, stderr = _run_torque_cli_command(command, cwd=cwd)
        stdout = stdout.split("\n") if stdout else []
        stderr = stderr.split("\n") if stderr else []
        sandbox_id = ""
        for line in stdout:
            line_dec = line.strip()
            if line_dec.startswith("Id:"):
                sandbox_id = line_dec.replace("Id: ", "")
            if not line_dec.endswith("sec]"):
                if sandbox_id and not line_dec == sandbox_id:
                    server.show_message_log(line_dec)

        error_msg = ""
        if stderr:
            # server.show_message_log('Error while starting the sandbox:')
            for line in stderr:
                # error_msg += line.decode().strip() + "\n"
                error_msg += line.strip() + "\n"
                # server.show_message_log(line.decode().strip())
            if error_msg:
                error_msg = "Error while starting the sandbox:\n" + error_msg
                server.show_message_log(error_msg)
        if error_msg:
            server.show_message(
                "Sandbox creation failed. Check the 'Torque' Output view for more details."
            )
        else:
            server.show_message(
                "Sandbox was created. See details in the Output view or Sandboxes explorer."
            )
            server.show_message_log(
                "Sandbox was created. View current status and more details using the Sandboxes explorer."
            )
    except Exception as ex:
        server.show_message_log(str(ex), msg_type=MessageType.Error)


@torque_ls.command(TorqueLanguageServer.CMD_LIST_TORQUE_PROFILES)
async def get_profiles(server: TorqueLanguageServer, *_):
    result = []
    keys = ["profile", "account", "space"]

    try:
        stdout, stderr = _run_torque_cli_command(
            "torque --disable-version-check configure list"
        )

    except Exception as ex:
        server.show_message(
            f"Unable to fetch profiles list, reason: {str(ex)}",
            msg_type=MessageType.Error,
        )
        return []

    lines = stdout.split("\n")

    for i in range(2, len(lines)):
        if lines[i]:
            data = lines[i].split()[:-1]
            if len(data) > 3 or len(data) < 2:
                server.show_message(
                    f"Wrong format of line: {data}", msg_type=MessageType.Error
                )
                return []

            if len(data) == 2:
                data.insert(1, "")

            result.append(dict(zip(keys, data)))

    return result


@torque_ls.command(TorqueLanguageServer.CMD_LIST_SANDBOXES)
async def list_sandboxes(server: TorqueLanguageServer, *_):
    active_profile = await _get_profile(server)

    if not active_profile:
        server.show_message(
            "Please have at least one profile set as the default one.",
            MessageType.Error,
        )
        return

    sbs = []

    try:
        stdout, stderr = _run_torque_cli_command(
            f"torque --disable-version-check --profile {active_profile} sb list --output=json"
        )

        if stderr:
            server.show_message(
                f"An error occurred while executing the command: {stderr}",
                MessageType.Error,
            )

        if stdout:
            sbs = json.loads(stdout)

    except Exception as ex:
        server.show_message(
            f"Unable to fetch Torque sandboxes. Reason: {str(ex)}", MessageType.Error
        )
    return sbs


@torque_ls.command(TorqueLanguageServer.CMD_LIST_BLUEPRINTS)
async def list_blueprints(server: TorqueLanguageServer, *_):
    active_profile = await _get_profile(server)

    if not active_profile:
        server.show_message(
            "Please have at least one profile set as the default one.",
            MessageType.Error,
        )
        return

    try:
        stdout, stderr = _run_torque_cli_command(
            f"torque --disable-version-check --profile {active_profile} bp list --output=json --detail"
        )

        if stderr:
            server.show_message(
                f"An error occurred while executing the command: {stderr}",
                MessageType.Error,
            )
        return stdout

    except Exception as ex:
        server.show_message(
            f"Unable to fetch Torque sandboxes. Reason: {str(ex)}", MessageType.Error
        )
        return None


@torque_ls.command(TorqueLanguageServer.CMD_TORQUE_LOGIN)
async def torque_login(server: TorqueLanguageServer, *args):
    if not args or not args[0]:
        server.show_message("No params for login provided", MessageType.Error)
        return 1

    params = args[0].pop()
    if " " in params.profile:
        server.show_message("Profile name cannot have spaces", MessageType.Error)
        return 1
    if " " in params.space:
        server.show_message("Space name cannot have spaces", MessageType.Error)
        return 1

    try:
        command = (
            "torque --disable-version-check configure set "
            f" -P {params.profile}"
            f" -a {params.account}"
            f" -s {params.space}"
        )

        if params.email and params.password:
            command = command + f" --login -e {params.email} -p {params.password}"

        elif params.token:
            command = command + f" -t {params.token}"

        _, stderr = _run_torque_cli_command(command)

        exit_code = 1 if "Login Failed" in stderr else 0
        if exit_code != 0:
            return "Login Failed"
        else:
            return None

    except Exception as ex:
        logging.error(ex)
        return


@torque_ls.command(TorqueLanguageServer.CMD_REMOVE_PROFILE)
async def remove_profile(server: TorqueLanguageServer, *args):
    if len(args[0]) == 0:
        server.show_message(
            "Profile was not provided",
            MessageType.Error,
        )
        return

    profile_name = args[0][0]
    try:
        _, _ = _run_torque_cli_command(
            f"torque --disable-version-check configure remove {profile_name}"
        )
        server.show_message(f"Profile '{profile_name}' deleted.")
        return True
    except Exception as ex:
        server.show_message(
            f"Failed to remove profile '{profile_name}'. Reason: {str(ex)}",
            MessageType.Error,
        )


@torque_ls.command(TorqueLanguageServer.CMD_GET_SANDBOX)
async def get_sandbox(server: TorqueLanguageServer, *args):
    if not args or not args[0]:
        server.show_message("No sandbox id provided", MessageType.Error)
        return 1

    active_profile = await _get_profile(server)

    if not active_profile:
        server.show_message(
            "Please have at least one profile set as the default one.",
            MessageType.Error,
        )
        return

    sb_id = args[0].pop()
    try:
        stdout, stderr = _run_torque_cli_command(
            f"torque --disable-version-check --profile {active_profile} sb get {sb_id} --output=json --detail"
        )
        if stderr:
            server.show_message(
                f"An error occurred while executing the command: {stderr}",
                MessageType.Error,
            )
        return stdout

    except Exception as ex:
        server.show_message(
            f"Failed to get status of sandbox {sb_id}. Reason: {str(ex)}",
            MessageType.Error,
        )


@torque_ls.command(TorqueLanguageServer.CMD_END_SANDBOX)
async def end_sandbox(server: TorqueLanguageServer, *args):
    if not args or not args[0]:
        server.show_message("No sandbox id provided", MessageType.Error)
        return 1

    active_profile = await _get_profile(server)

    if not active_profile:
        server.show_message(
            "Please have at least one profile set as the default one.",
            MessageType.Error,
        )
        return

    sb_id = args[0].pop()

    try:
        stdout, stderr = _run_torque_cli_command(
            f"torque --disable-version-check --profile {active_profile} sb end {sb_id}"
        )

        if stderr:
            server.show_message(
                f"An error occurred while executing the command: {stderr}",
                MessageType.Error,
            )
        return stdout

    except Exception as ex:
        server.show_message(
            f"Failed to end the sandbox {sb_id}. Reason: {str(ex)}", MessageType.Error
        )


@torque_ls.command(TorqueLanguageServer.CMD_VALIDATE_BLUEPRINT)
async def validate_blueprint(server: TorqueLanguageServer, *args):
    if len(args[0]) == 0:
        server.show_message(
            "Please validate the blueprint from the command in the blueprint file.",
            MessageType.Error,
        )
        return

    active_profile = await _get_profile(server)

    if not active_profile:
        server.show_message(
            "Please have at least one profile set as the default one.",
            MessageType.Error,
        )
        return

    blueprint_name = unquote(pathlib.Path(args[0][0]).name.replace(".yaml", ""))
    server.show_message("Validating blueprint: " + blueprint_name)
    server.show_message_log("Validating blueprint: " + blueprint_name)
    try:
        _, stderr = _run_torque_cli_command(
            f'torque --disable-version-check --profile {active_profile} bp validate "{blueprint_name}" --output=json',
            cwd=server.workspace.root_path,
        )

        if stderr:
            try:
                errors_json = json.loads(stderr)
                headers = ["Problem", "Details"]
                table = []
                for err in errors_json:
                    table.append(
                        [
                            "\n".join(textwrap.wrap(err["name"], width=40)),
                            "\n".join(textwrap.wrap(err["message"], width=60)),
                        ]
                    )

                server.show_message_log(
                    tabulate.tabulate(table, headers, tablefmt="simple")
                )
                server.show_message(
                    'Validation complete. Check the "Torque" Output view for any issues.'
                )
            except JSONDecodeError:
                server.show_message(
                    "Unable to get the list of issues. Try to validate blueprint using Torque CLI"
                )
        else:
            server.show_message_log(
                f"Validation completed. The blueprint '{blueprint_name}' and its dependencies are valid."
            )

    except Exception as ex:
        logging.error(ex)
