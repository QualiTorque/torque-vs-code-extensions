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

![auto-completions](https://user-images.githubusercontent.com/8643801/131506679-8726c8cc-701d-421c-bd8a-64fe8dc1fc5e.gif)

### Validation

There is quite a long list of things being validated by this extension including general yaml schema validation and more
complex dynamic checks. Some of them are the following:

- Validate if app/service mentioned in a blueprint exists
- Validate that variables mentioned in Torque files are defined in inputs section
- Allow accepting variables to specific nodes only
- Check existence of referenced files (scripts, terraform files)
- ... and many others

![validation](https://user-images.githubusercontent.com/8643801/131506669-7285ca9e-e3a6-4ded-831f-caf926e79752.gif)

### Document Links

In some parts of Torque documents you have links, and you can jump to the referenced files when ctrl(cmd) + click on them.
- In a blueprint file it opens relevant application/service YAML when clicking on their names.
- In service/application file you jump to referenced scripts

![links](https://user-images.githubusercontent.com/8643801/131506656-c63860a7-6828-4b8d-afd0-4ea51c1d36b5.gif)

## Getting Started

**Prerequisite:** you need to have **python>=3.6** installed on your system

- Install the extension from the Marketplace
- VS Code may require reload, make sure you do that
- If VS Code doesn't know where to find python you will need to previde its path in the appeared popup or
  directly in VS Code settings
- Open any folder with a Torque blueprint repo and enjoy developong with new features ;)

The extension should be triggered automatically when loading Torque's applications, blueprints or services YAMLs and it should avoid parsing
non-Torque YAML files.
