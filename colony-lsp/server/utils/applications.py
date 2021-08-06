import os
import logging
import pathlib
from server.utils.yaml_utils import format_yaml
from server.ats.parser import Parser, ParserError

APPLICATIONS = {}


def load_app_details(app_name: str, app_source: str):
    app_tree = Parser(document=app_source).parse()
    
    output = f"- {app_name}:\n"
    output += "    instances: 1\n"
    if app_tree.inputs_node:                        
        inputs = app_tree.inputs_node.nodes
        if inputs:
            output += "    input_values:\n"
            for input in inputs:
                if input.value:
                    output += f"      - {input.key.text}: {input.value.text}\n"
                else:
                    output += f"      - {input.key.text}: \n"    
    
    APPLICATIONS[app_name] = {
        'app_tree': app_tree,
        'app_completion': format_yaml(output)
    }


def reload_app_details(app_name, app_source):
    if APPLICATIONS: # if there is already a cache, add this file
        load_app_details(app_name, app_source)


def get_available_applications(root_folder: str):
    if APPLICATIONS:
        return APPLICATIONS
    else:
        apps_path = os.path.join(root_folder, 'applications')
        if os.path.exists(apps_path):
            for dir in os.listdir(apps_path):
                app_dir = os.path.join(apps_path, dir)
                if os.path.isdir(app_dir):
                    files = os.listdir(app_dir)
                    if f'{dir}.yaml' in files:
                        f = open(os.path.join(app_dir, f'{dir}.yaml'), "r")
                        source = f.read()
                        try:
                            load_app_details(app_name=dir, app_source=source)
                        except ParserError as e:
                            logging.warning(f"Unable to load application '{dir}.yaml' due to error: {e.message}")
                            continue
                        except Exception as e:
                            logging.warning(f"Unable to load appliiation '{dir}.yaml' due to error: {str(e)}")
                            continue
                    
        return APPLICATIONS


def get_available_applications_names():
    if APPLICATIONS:
        return list(APPLICATIONS.keys())
    else:
        return []


def get_app_scripts(app_path: str):
    scripts = []
    files = pathlib.Path(app_path.replace("file://", "")).parent.glob("./*")
    for file in files:
        if not file.name.endswith('.yaml'):
            scripts.append(pathlib.Path(file).name)

    return scripts


def get_app_inputs(app_name):
    if app_name in APPLICATIONS:
        app_tree = APPLICATIONS[app_name]["app_tree"]
        inputs = {}
        if app_tree.inputs_node:
            for input in app_tree.inputs_node.nodes:
                inputs[input.key.text] = input.value.text if input.value else None
        return inputs
    
    return []


def get_app_outputs(app_name):
    if app_name in APPLICATIONS:
        app_tree = APPLICATIONS[app_name]["app_tree"]
        if app_tree.outputs:
            outputs = [out.text for out in app_tree.outputs.nodes]
            return outputs
    
    return []
    