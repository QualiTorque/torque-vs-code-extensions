# VS Code Extension for Quali Torque

## Features

The Quali Torque language extension aims to ease life of Torque content creators by providing file validations, code completions and other editing tools available.

### Code auto-completion

- When designing a blueprint, under the applications' node, provide a list of applications. Once selected, it can provide
  all required fields (instance count, inputs, etc) 
- When designing an application, under the configuration initialization/start, provide the list of available scripts
  that exist in this app's folder.
- When designing a service, provide the variables file from that folder, once selected, add all the variables to the
  service file.
- When designing a blueprint/app/service, allow the auto-completion of inputs defined in this file 

### Validation

There is quite a long list of things being validated by this extension including general yaml schema validation and more
complex dynamic checks. Some of them are the following:

- Validate if app/service mentioned in a blueprint exists
- Validate that variables mentioned in Torque files are defined in inputs section
- Allow accepting variables to specific nodes only
- Check existence of referenced files (scripts, terraform files)
- ... and many others

### Document Links

In some parts of Torque documents you have links, and you can jump tp the referenced files when ctrl(cmd) + click on them.
- In a blueprint file it opens relevant application/service YAML when clicking on their names.
- In service/application file you jump to referenced scripts

## Getting Started

- Install the extension from the Marketplace
- VS Code may require reload, make sure you do that
- Make sure VS code knows the path to the python environment

The extension should be triggered automatically when loading YAML files and it should avoid parsing
non-Torque YAML files.
