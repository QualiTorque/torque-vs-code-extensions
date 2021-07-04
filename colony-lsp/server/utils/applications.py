import os
import pathlib
from server.ats.parser import AppParser
import yaml

APPLICATIONS = {}


def load_app_details(app_name: str, app_source: str):
    app_tree = AppParser(document=app_source).parse()
    app_file = yaml.load(app_source, Loader=yaml.FullLoader)
    
    output = f"{app_name}:\n"
    output += "  instances: 1\n"                        
    inputs = app_file['inputs'] if 'inputs' in app_file else None
    if inputs:
        output += "  input_values:\n"
        for input in inputs:
            if isinstance(input, str):
                output += f"    - {input}: \n"
            elif isinstance(input, dict):
                for k,v in input.items():
                    output += f"    - {k}: {v}\n"
    aaa = yaml.load(output, Loader=yaml.FullLoader)
    bbb = yaml.dump(aaa)
    print(bbb)
    
    APPLICATIONS[app_name] = {
        'app_tree': app_tree,
        'app_completion': "- " + bbb.replace(": null", ": ")
    }


def reload_app_details(app_name, app_source):
    if APPLICATIONS and app_name not in APPLICATIONS: # if there is already a cache, add this file
        # APPLICATIONS[app_name] = app_tree
        load_app_details(app_name, app_source)


def get_available_applications(root_folder: str):
    if APPLICATIONS:
        return APPLICATIONS
    else:
        apps_path = os.path.join(root_folder, 'applications')
        for dir in os.listdir(apps_path):
            app_dir = os.path.join(apps_path, dir)
            if os.path.isdir(app_dir):
                files = os.listdir(app_dir)
                if f'{dir}.yaml' in files:
                    f = open(os.path.join(app_dir, f'{dir}.yaml'), "r")
                    source = f.read() 
                    load_app_details(app_name=dir, app_source=source)
                    
        return APPLICATIONS


def get_app_scripts(app_dir_path: str):
    scripts = []
    files = pathlib.Path(app_dir_path.replace("file://", "")).parent.glob("./*")
    for file in files:
        if not file.name.endswith('.yaml'):
            scripts.append(pathlib.Path(file).name)

    return scripts


def get_app_outputs(app_name):
    if app_name in APPLICATIONS:
        app_tree = APPLICATIONS[app_name]["app_tree"]
        outputs = [out.text for out in app_tree.outputs]
        return outputs
    else:
        return None
    