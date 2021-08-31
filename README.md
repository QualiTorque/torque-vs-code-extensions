# VS Code Extension for Torque

The Quali Torque language extension aims to ease the life of the Torque content creators by providing file validations, code completions and other editing tools available.

## Features

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

There is quite a long list of things being validated by this extension including general YAML schema validation and more
complex dynamic checks. Some of them are the following:

- Validate if an app/service mentioned in a blueprint exists
- Validate that variables mentioned in Torque files are defined in the inputs section
- Allow accepting variables to specific nodes only
- Check existence of referenced files (scripts, terraform files)
- ... and many others

![validation](https://user-images.githubusercontent.com/8643801/131506669-7285ca9e-e3a6-4ded-831f-caf926e79752.gif)

### Document Links

In some parts of Torque documents you have links, and you can jump to the referenced files when ctrl(cmd) + click on them.
- In a blueprint file, it opens the relevant application/service YAML when clicking on their names.
- In a service/application file you can jump to the referenced scripts

![links](https://user-images.githubusercontent.com/8643801/131506656-c63860a7-6828-4b8d-afd0-4ea51c1d36b5.gif)

## Getting Started

**Prerequisite:** you need to have **python>=3.6** installed on your system

- Install the extension from the Marketplace
- VS Code may require you to reload it. Make sure you do that.
- If VS Code can't find the python you have installed, you will need to provide its path in the appeared popup 
  or directly in VS Code settings (under pyhon.pythonPath)
- Open any folder with a Torque blueprint repository and get an enhanced experience working on your Torque files!

The extension should be triggered automatically when loading Torque's blueprints, applications, or services YAMLs located in a [blueprint repository folder structure](https://community.qtorque.io/developing-blueprints-61/setting-up-a-blueprint-repository-258).
