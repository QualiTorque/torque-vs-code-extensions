import logging
import os
import re
import pathlib
import yaml
from server.ats.parser import Parser, ParserError
from server.utils.yaml_utils import format_yaml

SERVICES = {}


def get_available_services(root_folder: str = None):
    if SERVICES:
        return SERVICES
    else:
        if root_folder:
            srv_path = os.path.join(root_folder, 'services')
            if os.path.exists(srv_path):
                for dir in os.listdir(srv_path):
                    srv_dir = os.path.join(srv_path, dir)
                    if os.path.isdir(srv_dir):
                        files = os.listdir(srv_dir)
                        if f'{dir}.yaml' in files:
                            f = open(os.path.join(srv_dir, f'{dir}.yaml'), "r")
                            source = f.read()
                            load_service_details(srv_name=dir, srv_source=source)

            return SERVICES
        else:
            return None


def get_available_services_names():
    if SERVICES:
        return list(SERVICES.keys())
    else:
        return []


def load_service_details(srv_name: str, srv_source):
    srv_tree = None
    output = None
    try:
        srv_tree = Parser(document=srv_source).parse()

        output = f"- {srv_name}:\n"
        inputs = srv_tree.get_inputs()
        if inputs:
            output += "    input_values:\n"
            for input in inputs:
                if input.value:
                    output += f"      - {input.key.text}: {input.value.text}\n"
                else:
                    output += f"      - {input.key.text}: \n"
    except ParserError as e:
        logging.warning(f"Unable to load service '{dir}.yaml' due to error: {e.message}")
    except Exception as e:
        logging.warning(f"Unable to load service '{dir}.yaml' due to error: {str(e)}")

    SERVICES[srv_name] = {
        "tree": srv_tree,
        "completion": format_yaml(output) if output else None
    }


def reload_service_details(srv_name, srv_source):
    if SERVICES:  # if there is already a cache, add this file
        load_service_details(srv_name, srv_source)


def remove_service_details(srv_name):
    if SERVICES: # if there is already a cache, remove this file
        if srv_name in SERVICES:
            SERVICES.pop(srv_name)
            

def get_vars_from_tfvars(file_path: str):
    vars = []
    with open(file_path, "r") as f:
        content = f.read()
        vars = re.findall(r"(^.+?)\s*=", content, re.MULTILINE)

    return vars


def get_service_vars(service_dir_path: str):
    with open(service_dir_path.replace("file://", ""), 'r') as stream:
        try:
            yaml_obj = yaml.load(stream, Loader=yaml.FullLoader)  # todo: refactor
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
                    "variables": get_vars_from_tfvars(file)
                }
                tfvars.append(item)

        return tfvars

    return []


def get_service_inputs(srv_name):
    if srv_name in SERVICES:
        srv_tree = SERVICES[srv_name]["tree"]
        if srv_tree and srv_tree.inputs_node:
            inputs = {}
            for input in srv_tree.get_inputs():
                inputs[input.key.text] = input.value.text if input.value else None
            return inputs

    return {}


def get_service_outputs(srv_name):
    if srv_name in SERVICES:
        srv_tree = SERVICES[srv_name]["tree"]
        outputs = [out.text for out in srv_tree.get_outputs()]
        return outputs

    return []
