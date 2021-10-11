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

In some parts of Torque configuration files you have links, and you can jump to the referenced files by holding down the __[Ctrl]__ keyboard key and clicking the link.
- In a blueprint file, it opens the relevant application/service YAML when clicking the file's name.
- From a service/application file, you can jump to the referenced scripts.

![links](https://user-images.githubusercontent.com/8643801/131506656-c63860a7-6828-4b8d-afd0-4ea51c1d36b5.gif)

### Interactive features

This extension also enables you to interact with Torque directly. You can ask Torque to validate a local blueprint, start sandbox from it and explore and manage resources that are currenly available in Torque.

In the activity bar you have a new Torque menu item where you will find information about active sandboxes and enabled blueprints available in Torque.

![activitybar](https://user-images.githubusercontent.com/8643801/136196489-72b24601-075a-45d0-8230-8be2975ad7e6.png)

In order to see and interact with information in these views, this extension utilizes the Torque CLI (which is also installed as a dependency). If you're already using it, and have [profiles configured](https://github.com/QualiSystemsLab/colony-cli#configuration) you will see them appear in the UI.
If you don't have any profiles there, or have never used it, you can add them from the Profiles explorer (using the + button, or from the Login to Torque messages in the Blueprints/Sandboxes explorers), and logging into Torque using your email credentials or a token, directly from VSCode. 

![login](https://user-images.githubusercontent.com/8643801/136199312-3f3e34a1-4373-470a-9438-ba88ac2e7dbf.png)

#### Switching between profiles

You can change the active profile with the checkmark buttons in the Profiles explorer. Once selected, the different explorers will be updated accordingly. All the next actions will be performed within an account and space mapped to this profile and the explorers trees will get updated accordingly.

![switch](https://user-images.githubusercontent.com/8643801/136202940-aea95f49-3ff9-4bb2-8bc2-c4b1b54f61a0.gif)

#### Starting sandboxes

You can start a sandbox in Torque from a blueprint file that is currently open in the IDE. or by selecting any of the available blueprints in the Blueprints explorer (only valid and published blueprints are displayed there). All the default values for the parameters inputs and artifacts are taken from the blueprint's definitions.

![start-sandbox](https://user-images.githubusercontent.com/8643801/136235308-1c82468e-59da-4e08-8867-83a0a0534be2.gif)

#### Server Blueprint Validation

Although a local, real-time syntax validation finds the most common errors in your blueprint/application/service files, you can still ask Torque to check for errors on the server-side. Open any of the blueprint's files in your repository and use the code lens command to start the validation:

![validation](https://user-images.githubusercontent.com/8643801/136206637-b4a8f19c-1db4-47dd-82f8-8bf8976d0303.gif)

## Getting Started

**Prerequisite:** 
* **python>=3.6** installed on your system.

- Install the extension from the Marketplace.
- VS Code may require you to reload it. Make sure you do that.
- If VS Code can't find the python you have installed, you will need to provide its path in the popup that appears 
  or directly in VS Code settings (under __pyhon.pythonPath__)
- Open any folder with a Torque blueprint repository and get an enhanced experience working on your Torque files!

The extension will be activated automatically when loading Torque's blueprint, application, or service YAMLs located in a [blueprint repository folder structure](https://community.qtorque.io/developing-blueprints-61/setting-up-a-blueprint-repository-258), or when opening the Torque view in the activity bar.
