/* -------------------------------------------------------------------------
 * Original work Copyright (c) Microsoft Corporation. All rights reserved.
 * Original work licensed under the MIT License.
 * See ThirdPartyNotices.txt in the project root for license information.
 * All modifications Copyright (c) Open Law Library. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License")
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http: // www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 * ----------------------------------------------------------------------- */
"use strict";

import * as net from "net";
import * as path from "path";
import { ExtensionContext, workspace, languages } from "vscode";
import { installLSWithProgress } from "./setup";
import {
    LanguageClient,
    LanguageClientOptions,
    ServerOptions,
} from "vscode-languageclient/node";
import {
    activateYamlExtension,
    addSchemasToYamlConfig
} from './yamlHelper';

let client: LanguageClient;

function getClientOptions(): LanguageClientOptions {
    return {
        // Register the server for plain text documents
        documentSelector: [
            { scheme: "file", language: "yaml" },
            // { scheme: "untitled", language: "yaml" },
        ],
        outputChannelName: "Torque Language Server",
        synchronize: {
            // Notify the server about file changes to '.yaml files contain in the workspace
            fileEvents: workspace.createFileSystemWatcher("**/*.yaml"),
        },
    };
}

function isStartedInDebugMode(): boolean {
    return process.env.VSCODE_DEBUG_MODE === "true";
}

function startLangServerTCP(addr: number): LanguageClient {
    const serverOptions: ServerOptions = () => {
        return new Promise((resolve /*, reject */) => {
            const clientSocket = new net.Socket();
            clientSocket.connect(addr, "127.0.0.1", () => {
                resolve({
                    reader: clientSocket,
                    writer: clientSocket,
                });
            });
        });
    };

    return new LanguageClient(
        `tcp lang server (port ${addr})`,
        serverOptions,
        getClientOptions()
    );
}

function startLangServer(
    command: string,
    args: string[],
    cwd: string
): LanguageClient {
    const serverOptions: ServerOptions = {
        args,
        command,
        options: { cwd },
    };
    return new LanguageClient(command, serverOptions, getClientOptions());
}

async function activateYamlFeatures(context: ExtensionContext) {
    await addSchemasToYamlConfig(context.extensionPath);
    await activateYamlExtension();
}

export async function activate(context: ExtensionContext) {
    if (isStartedInDebugMode()) {
        // Development - Run the server manually
        client = startLangServerTCP(2087);
    } else {
        // Production - Client is going to run the server (for use within `.vsix` package)
        const cwd = path.join(__dirname, "..", "out", "server");
        const pythonPath = workspace
            .getConfiguration("python")
            .get<string>("pythonPath");

        if (!pythonPath) {
            throw new Error("`python.pythonPath` is not set");
        }
        const python = await installLSWithProgress(context);
        client = startLangServer(python, ["-m", "server"], cwd);
    }

    activateYamlFeatures(context);    
    context.subscriptions.push(client.start());
}

export function deactivate(): Thenable<void> {
    return client ? client.stop() : Promise.resolve();
}
