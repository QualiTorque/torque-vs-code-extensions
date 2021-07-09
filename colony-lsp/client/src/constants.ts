
import { join } from "path";
import { extensions } from "vscode";
//import { ICommand } from "./interfaces";
//import { getCommands } from "./utils";


// Extension info
export const EXTENSION_JSON = extensions.getExtension("Quali.colony-language-extension").packageJSON;
export const EXTENSION_NAME = EXTENSION_JSON.displayName;
export const EXTENSION_PATH = EXTENSION_JSON.extensionLocation.fsPath;

export const IS_WIN = process.platform === "win32";
export const LS_VENV_NAME = "colony-lsp";
export const LS_VENV_PATH = join(EXTENSION_PATH, LS_VENV_NAME);

export const COLONY_LS_SERVER = "colony_lsp"