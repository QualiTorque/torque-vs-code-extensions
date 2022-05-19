# VS Code Extension for Torque

The Quali Torque language extension aims to ease the life of the Torque content creators by providing file validations, code completions and more.

## Features

### Code auto-completion

- When designing a blueprint, you can get code suggestions based on a document schema. For example, it may help you to figure out
what other properties could be added to document.
- When designing a grain, under the __depends-on__ field, intellisense can provide you with a list of the available grains names.

![completions](https://user-images.githubusercontent.com/8643801/169277560-b0b8889d-9258-4f0a-8dc8-02ae38512107.gif)

### Validation

This extension runs a pretty long list of validations, including general YAML schema validations and more
complex dynamic checks. Some of them include:

- Validate that grains or inputs mentioned in expressions are defined
- Validate that expressions are being used in the allowed places only
- Grains depends-on validations 

And more validations coming soon...

### Document Links

Coming soon...

### Interactive features

Coming soon...

## Getting Started

> **_NOTE:_** This extension works with Torque's **spec_version=2**. The version 1 has been deprecated. If you are still interested in working with spec 1, the latest stable version of extension available on Marketplace is **0.0.12**

**Prerequisite:** 
* **python>=3.6** installed on your system.

- Install the extension from the Marketplace.
- VS Code may require you to reload it. Make sure you do that.
- If VS Code can't find the python you have installed, you will need to provide its path in the popup that appears 
  or directly in VS Code settings (under __pyhon.pythonPath__)
- Open any folder with a Torque blueprint repository and get an enhanced experience working on your Torque files!

The extension will be activated automatically when loading Torque's blueprint, application, or service YAMLs located in a [blueprint repository folder structure](https://community.qtorque.io/developing-blueprints-61/setting-up-a-blueprint-repository-258), or when opening the Torque view in the activity bar.
