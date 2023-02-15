# Change Log

## [0.3.2](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.3.1...v0.3.2) (2023-02-01)

* minor schema updates

## [0.3.1](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.3.0...v0.3.1) (2022-11-18)

* set a VS Code user-agent

## [0.3.0](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.2.4...v0.3.0) (2022-11-14)

* rename sandboxes to environments
* blueprint schema updates
* bump-up torque-cli version

## [0.2.4](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.2.3...v0.2.4) (2022-10-24)

* return blueprint validation feature back

## [0.2.3](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.2.2...v0.2.3) (2022-08-02)

* schema updates:
  - new grains support
  - blueprint 'input' property updates
* add support for blueprint source type

## [0.2.2](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.2.1...v0.2.2) (2022-07-04)

* some fixes
* schema updates:
  - fix env_vars
  - add outputs 'kind' prop
  - add inputs 'sensitive' prop

## [0.2.1](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.2.0...v0.2.1) (2022-06-08)

* fix bug with grain completer
* hide autogen prefix in blueprint explorer

## [0.2.0](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.20...v0.2.0) (2022-06-07)

* some schema updates
* switch to new torque-cli
* return UI part of extension

## [0.0.20](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.19...v0.0.20) (2022-05-25)

* minor fixes

## [0.0.19](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.18...v0.0.19) (2022-05-20)

* added validation for depend-on duplicates
* added validation for grain inputs duplicates
* added warning for unused blueprint inputs

## [0.0.18](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.17...v0.0.18) (2022-05-18)

* some schema updates

## [0.0.17](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.16...v0.0.17) (2022-05-18)

* check duplicates in grains outputs
* fix several bugs around depends-on field
* update schema

## [0.0.16](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.12...v0.0.16) (2022-05-16)

Add Torque spec 2 support [WIP]

* added init json schema for new spec
* added parser/tree 
* implemented server-side validation for grain dependecies and expressions
* auto-completions for grains deps
* disabled UI blueprints/sandboxes explorers (temporary)
 
[NOTE] The last stable version with spec version 1 is 0.0.12

## [0.0.12](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.11...v0.0.12) (2022-04-13)

Add possible_values support

* AST and schema were updated
* Validation and completion features were added

## [0.0.11](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.10...v0.0.11) (2021-12-24)

Add python 3.10 support

## [0.0.10](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.9...v0.0.10) (2021-12-01)

Cleanups and improvements to the extension to provide you with the best experience and performance.
### Bug Fixes

* Fixed an issue with starting a sandbox or validating a local blueprint that failed on Windows
* Hide Terraform Blueprints until they will be fully supported

### Features

* Add a notification when the validation of a blueprint completes

## [0.0.9](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.8...v0.0.9) (2021-11-15)

Cleanups and improvements to the extension to provide you with the best experience and performance.
### Bug Fixes

* Fixed an issue with starting a sandbox from blueprint with whitespace characters

### Features

* A few more completions in Blueprints for artifacts, depends_on and rules


## [0.0.8](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.7...v0.0.8) (2021-11-10)

### Interactive features
A new Torque icon is now available in the sidebar, opening the access to the creation of Profiles, view online Blueprints, and view of active Sandboxes.
You can create one or more profiles to connect you to a certain account/space and switch between the profiles as needed.

In a blueprint file, you can now ask to Validate with Torque, to check if the current state of the blueprint and all of its dependencies are valid for use with Torque - this can be done without committing the changes to the online repository branch that Torque is monitoring.

Also in a blueprint file, in a similar way, you can start a sandbox from the currently modified files, and check that everything works well before committing the changes or merging them to the monitored branch.

A few more code completions are available and some other bug fixes are included.



## [0.0.7](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.6...v0.0.7) (2021-08-31)


### Bug Fixes

* Fix an issue with installation through the marketplace



## [0.0.6](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.5...v0.0.6) (2021-03-10)


## Rebrand as Torque VS code extension

### Bug Fixes

* A few more validation fixes
* Fix the installation process for Windows whenever a python path is provided



## [0.0.5](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.4...v0.0.5) (2021-08-24)

### Bug Fixes

* Update for the completions triggers to also work on vs code 1.59+
* Schema updates for additional allowed properties
* Schema fixes for Instances validation
* Fix for allowed colony.repos.current variables
* Fix for allowed colony.parameters variables
* Allow artifacts to be an empty list
* Tracking changes in the workspace to update the validations upon changes
* Services - don’t warn about unused inputs if they are used by name only in the variable values

### Features

#### Blueprints
* Additional completions for allowed colony variables
* Additional validation for missing dependencies

#### All
* Completion for variables from inputs defined in the file
* Additional validation on reserved words (torque/colony cannot be used as an input prefix)
* Validate that a variable is used only in places it’s allowed


## [0.0.4](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.3...v0.0.4) (2021-08-10)

### Bug Fixes

* Blueprints:
  * Fix schema for app/service input values
  * Skip inputs validations when there are no inputs
  * Fix for blueprints that failed to load correctly
  * Fix for document links in blueprints not showing up sometimes
  * Fix for document links path in Windows
  * Show apps that are having issues instead of failing to find them
* Services:
  * Fix schema to only allow inputs with values or just input name
* Applications:
  * Fix schema to only allow inputs with values or just input name
* All:
  * Better handling of empty files
  * Better yaml parsing, showing errors on unknown nodes instead of breaking the parse


### Features

* Blueprints:
  * Show apps/services that are having issues instead of failing to find them
* Services:
  * Completions for var_file with available tfvars files
* Applications:
  * Completions for available script files


## [Older versions](https://github.com/QualiTorque/torque-vs-code-extensions/compare/v0.0.2...v0.0.3)