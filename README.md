# VS Code Extension for Torque

The Quali Torque language extension aims to ease the life of the Torque content creators by providing file validations, code completions and more.

## Features

### Code auto-completion

- When designing a blueprint, under the __applications__ node, provide a list of applications. Once selected, it can provide
  all required fields (instance count, inputs, etc) 
- When designing an application, under the __configuration > initialization__ or __configuration > start__ node, provide the list of available scripts
  that exist in this application's folder.
- When designing a service, provide the variables file from that folder. Once selected, add all the variables to the
  service file.
- When designing a blueprint/application/service, allow the auto-completion of inputs defined in this file.

![auto-completions](https://user-images.githubusercontent.com/8643801/131506679-8726c8cc-701d-421c-bd8a-64fe8dc1fc5e.gif)

### Validation

This extension runs a pretty long list of validations, including general YAML schema validations and more
complex dynamic checks. Some of them include:

- Validating the existence of an application/service mentioned in a blueprint
- Validating that variables mentioned in Torque files are defined in the __inputs__ node of the YAML
- Allowing the acceptance of variables to specific nodes only
- Checking the existence of referenced files (scripts, terraform files)
- ... and many others

![validation](https://user-images.githubusercontent.com/8643801/131506669-7285ca9e-e3a6-4ded-831f-caf926e79752.gif)

### Document Links

In some parts of Torque configuration files you have links, and you can jump to the referenced files by holding down the __[Ctrl]__ keuboard key and clicking the link.
- In a blueprint file, it opens the relevant application/service YAML when clicking the file's name.
- From a service/application file, you can jump to the referenced scripts.

![links](https://user-images.githubusercontent.com/8643801/131506656-c63860a7-6828-4b8d-afd0-4ea51c1d36b5.gif)

## Getting Started

**Prerequisite:** 
* **python>=3.6** installed on your system

- Install the extension from the Marketplace.
- VS Code may require you to reload it. Make sure you do that.
- If VS Code can't find the python you have installed, you will need to provide its path in the popup that appears 
  or directly in VS Code settings (under __pyhon.pythonPath__)
- Open any folder with a Torque blueprint repository and get an enhanced experience working on your Torque files!

The extension should be triggered automatically when loading Torque's blueprint, application, or service YAMLs located in a [blueprint repository folder structure](https://community.qtorque.io/developing-blueprints-61/setting-up-a-blueprint-repository-258).
