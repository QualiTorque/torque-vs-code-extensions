
import os
import re
import pathlib
import yaml


def get_available_services(root_folder: str, cached_srv: list):
    if cached_srv:
        return cached_srv
    else:
        srv_path = os.path.join(root_folder, 'services')
        for dir in os.listdir(srv_path):
            srv_dir = os.path.join(srv_path, dir)
            if os.path.isdir(srv_dir):
                files = os.listdir(srv_dir)
                if f'{dir}.yaml' in files:
                    load_service_details(srv_name=dir, file_path=os.path.join(srv_dir, f'{dir}.yaml'), cached_srv=cached_srv)

        return cached_srv


def load_service_details(srv_name: str, file_path: str, cached_srv: list):
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
    cached_srv[srv_name] = output



def get_vars_from_tfvars(file_path: str):
    vars = []
    with open(file_path, "r") as f:
        content = f.read()
        vars = re.findall(r"(^.+?)\s*=", content, re.MULTILINE)
        
    return vars


def get_service_vars(service_dir_path: str):
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
                    "variables": get_vars_from_tfvars(file)
                }
                tfvars.append(item)

        return tfvars
    
    return []