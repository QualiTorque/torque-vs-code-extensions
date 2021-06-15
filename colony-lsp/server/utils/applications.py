import os
import pathlib
import yaml

def load_app_details(app_name: str, file_path: str, cached_apps: list):
    output = f"- {app_name}:\n"
    output += "  instances: 1\n"                        
    with open(file_path.replace("file://", ""), "r") as file:
        app_file = yaml.load(file, Loader=yaml.FullLoader)
        inputs = app_file['inputs'] if 'inputs' in app_file else None
        if inputs:
            output += "  input_values:\n"
            for input in inputs:
                if isinstance(input, str):
                    output += f"      - {input}: \n"
                elif isinstance(input, dict):
                    for k,v in input.items():
                        output += f"  - {k}: {v}\n"
    cached_apps[app_name] = output


def get_available_applications(root_folder: str, cached_apps: list):
    if cached_apps:
        return cached_apps
    else:
        apps_path = os.path.join(root_folder, 'applications')
        for dir in os.listdir(apps_path):
            app_dir = os.path.join(apps_path, dir)
            if os.path.isdir(app_dir):
                files = os.listdir(app_dir)
                if f'{dir}.yaml' in files:
                    load_app_details(app_name=dir, file_path=os.path.join(app_dir, f'{dir}.yaml'), cached_apps=cached_apps)
                    
        return cached_apps


def get_app_scripts(app_dir_path: str):
    scripts = []
    files = pathlib.Path(app_dir_path.replace("file://", "")).parent.glob("./*")
    for file in files:
        if not file.name.endswith('.yaml'):
            scripts.append(pathlib.Path(file).name)

    return scripts
