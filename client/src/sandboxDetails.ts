import * as vscode from 'vscode'
import { ProgressLocation, window } from "vscode";
import { Sandbox } from './models';
import { ProfilesManager } from './profilesManager';
import { getNonce } from './utils'


function getWebviewOptions(extensionUri: vscode.Uri): vscode.WebviewOptions {
	return {
        // Enable javascript in the webview
		enableScripts: true,

		// And restrict the webview to only loading content from our extension's `media` directory.
		localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
	};
}

/**
 * Manages sandbox details webview panels
 */
export class SandboxDetailsPanel {
	/**
	 * Track the currently panel. Only allow a single panel to exist at a time.
	 */
	public static currentPanel: SandboxDetailsPanel | undefined;

	public static readonly viewType = 'sandboxDetails';

	private readonly _panel: vscode.WebviewPanel;
	private readonly _extensionUri: vscode.Uri;

    private _sandbox_id: string;
    private _sandbox_name: string;
    private _blueprint_name: string;
    private _sandbox_details: string;
    private _disposables: vscode.Disposable[] = [];

	public static createOrShow(extensionUri:vscode.Uri, sandbox_id:string, sandbox_name:string, blueprint_name:string) {
		const column = vscode.window.activeTextEditor
			? vscode.window.activeTextEditor.viewColumn
			: undefined;

		// If we already have a panel, show it.
		if (SandboxDetailsPanel.currentPanel) {
			SandboxDetailsPanel.currentPanel.updatePanel(sandbox_id, sandbox_name, blueprint_name);
            SandboxDetailsPanel.currentPanel._panel.reveal(column);
            return;
		}

		// Otherwise, create a new panel.
		const panel = vscode.window.createWebviewPanel(
			SandboxDetailsPanel.viewType,
			'Sandbox Details',
			column || vscode.ViewColumn.One,
			getWebviewOptions(extensionUri),
		);
		SandboxDetailsPanel.currentPanel = new SandboxDetailsPanel(panel, extensionUri, sandbox_id, sandbox_name, blueprint_name);
	}

	private async reloadSandbox() {
        let details = new Map();
        const active_profile = (ProfilesManager.getInstance().getActive() === undefined) ? "" : ProfilesManager.getInstance().getActive().label

        return window.withProgress({location: ProgressLocation.Notification}, (progress): Promise<string> => {
            return new Promise<string>(async (resolve) => {
                progress.report({ message: "Loading sandbox details" });
                await vscode.commands.executeCommand('get_sandbox', this._sandbox_id, active_profile )
                .then(async (result:string) => {
                    if (result.length > 0)
                        details.set('status', result)
                        this._sandbox_details = result;
                        this._update();
                })
                resolve("")
            })
        })
	}

    private async endSandbox() {
        var sb = new Sandbox(
            this._sandbox_name,
            vscode.TreeItemCollapsibleState.None,
            this._sandbox_id,
            this._blueprint_name)
                                            
        vscode.commands.executeCommand('sandboxesExplorerView.endSandbox', sb)
            .then(() => {
                this._panel.dispose()
            })
    }

	private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, sandbox_id:string, sandbox_name:string, blueprint_name: string) {
		this._panel = panel;
		this._extensionUri = extensionUri;
        this._sandbox_id = sandbox_id;
        this._sandbox_name = sandbox_name;
        this._blueprint_name = blueprint_name;
        this._sandbox_details = null;
        
		// Set the webview's initial html content
		this._update();
        // Get updated information
        this.reloadSandbox();

		// Listen for when the panel is disposed
		// This happens when the user closes the panel or when the panel is closed programmatically
		this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

		// Handle messages from the webview
		this._panel.webview.onDidReceiveMessage(
			message => {
				switch (message.command) {
					case 'alert':
						vscode.window.showErrorMessage(message.text);
						return;
                    case 'run-command':
                        if (message.name == 'reload-sandbox') {
                            this.reloadSandbox();
                        }
                        else if (message.name == 'end-sandbox') {
                            this.endSandbox();
                        }
                        return;
				}
			},
			null,
			this._disposables
		);
	}

    public updatePanel(sandbox_id:string, sandbox_name:string, blueprint_name:string) {
        this._sandbox_id = sandbox_id;
        this._sandbox_name = sandbox_name;
        this._blueprint_name = blueprint_name;
        this._sandbox_details = null;

		// Set the webview's initial html content
		this._update();

        // Get updated information
        this.reloadSandbox();
    }

	public dispose() {
		SandboxDetailsPanel.currentPanel = undefined;

		// Clean up our resources
		this._panel.dispose();

		while (this._disposables.length) {
			const x = this._disposables.pop();
			if (x) {
				x.dispose();
			}
		}
	}

	private _update() {
		const webview = this._panel.webview;

		this._panel.title = 'Sandbox Details';
		this._panel.webview.html = this._getHtmlForWebview(webview);
	}

    private _getHtmlForWebview(webview: vscode.Webview) {
        const stylesPathMainPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'vscode.css');
        const stylesMainUri = webview.asWebviewUri(stylesPathMainPath);
        const nonce = getNonce();

        const htmlHeader = `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">

            <!--
                Use a content security policy to only allow loading images from https or from our extension directory,
                and only allow scripts that have a specific nonce.
            -->
            <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; img-src ${webview.cspSource} https:; script-src 'nonce-${nonce}';">

            <meta name="viewport" content="width=device-width, initial-scale=1.0">

            <link href="${stylesMainUri}" rel="stylesheet">

            <title>Sandbox Details</title>
            
        </head>`

        var closeHtml = "</html>"

        var htmlBody = "";
        if (!this._sandbox_details)
        {
            htmlBody = `<body>
                        <div style="vertical-align: top; display: inline-block; margin-top: 5px">
                        <h2>${this._sandbox_name}</h2>
                        <h3>Blueprint: ${this._blueprint_name}</h3>
                        <br/>
                        </div>
                        <div style="vertical-align: top;">
                        <h4>Loading details...</h4>
                        </div>
                        </body>`;
        }
        else
        {            
            // htmlBody = this._getMainBody(nonce)
            htmlBody = this._getBaseInfo(nonce)
        }
        return htmlHeader + htmlBody + closeHtml;
    }

    private _isEmpty(obj) {
        for (var j in obj) { return false }
        return true;
    }


    private _getBaseInfo(nonce:string) {
        const sandboxJson = JSON.parse(this._sandbox_details);

        const acct = ProfilesManager.getInstance().getActive().account
        const space = ProfilesManager.getInstance().getActive().space
    
        var generalHtml = "<table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        generalHtml += "<tr><td width='180px'>" + "ID" + "</td><td>" + this._sandbox_id + "</td></tr>";
        generalHtml += "<tr><td width='180px'>" + "Status" + "</td><td>" + sandboxJson.sandbox_status + "</td></tr>";
        generalHtml += "<tr><td width='180px'>" + "End time" + "</td><td>" + sandboxJson.scheduled_end_time + "</td></tr>";
    
        if (acct !== "") {
            const sandbox_url = `https://${acct}.qtorque.io/${space}/sandboxes/${this._sandbox_id}`
            generalHtml += "<tr><td width='180px'><a href='" + sandbox_url +"' target='_blank'/>" + "Open in Torque" + "</td><td></td></tr>";
        }
    
        generalHtml += "</table>";

        if (sandboxJson.applications.length > 0) {
            var shortcutsHtml = "<b>Quick Links</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
            for (var i = 0; i < sandboxJson.applications.length; i++) {
                let appName = sandboxJson.applications[i]['name'];
                let shortcuts = sandboxJson.applications[i]['shortcuts'];

                if (shortcuts.length > 0) {
                    shortcutsHtml += `<tr><td width='180px'>${appName}</td>`;

                    for (var j = 0; j < shortcuts.length; j++)
                        shortcutsHtml += `<td><a href='${shortcuts[j]}' target='_blank'/>link${j+1}</a></td>`;

                    shortcutsHtml += "<td></tr>"
                }
            }
            shortcutsHtml += "</table><br/>"; 
        } else
            shortcutsHtml = "";

        if (sandboxJson.inputs.length > 0) {
            var inputsHtml = "<b>Inputs</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";

            for (var i=0; i<sandboxJson.inputs.length; i++)
            {
                inputsHtml += "<tr><td width='180px'>" + sandboxJson.inputs[i]['name'] + "</td>";
                inputsHtml += "<td>" + (sandboxJson.inputs[i]['display_style'] == 'masked' ? '******' : sandboxJson.inputs[i]['value']) + "</td><td></tr>";
            }
            inputsHtml += "</table><br/>";
        } else 
            var inputsHtml = "";

        if (!this._isEmpty(sandboxJson.artifacts)) {
            var artifactsHtml = "<b>Artifacts</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
            for (const [key, value] of Object.entries(sandboxJson.artifacts)) {
                artifactsHtml += "<tr><td width='180px'>" + key  + "</td><td>" + value + "</td></tr>";
            }
            artifactsHtml += "</table>";
        }
        else 
            var artifactsHtml = "";
        
        const html = `
            <body>
            <div style="vertical-align: top; display: inline-block; margin-top: 5px">
            <h2>${this._sandbox_name}</h2>
            <h3>Blueprint: ${this._blueprint_name}</h3>
            <br/>
            </div>
            <div style="vertical-align: top; display: inline-block; float:right; margin-top: 5px">
            <input type='button' id='reload-btn' value='Refresh' style="width:100px;display: inline-block;">
            &nbsp;
            <input type='button' id='end-btn' value='End Sandbox' style="width:100px;display: inline-block;">
            </div>
            <div style="vertical-align: top;">
            ${generalHtml}
            <br/>
            ${shortcutsHtml}
            ${inputsHtml}
            ${artifactsHtml} 
            </div>              
            </body>`;
        
        const script = `
            <script nonce="${nonce}">
            const vscode = acquireVsCodeApi();
            document.getElementById("reload-btn").addEventListener("click", function() {
                vscode.postMessage({
                    command: 'run-command',
                    name: 'reload-sandbox'                 
                });
            });
            document.getElementById("end-btn").addEventListener("click", function() {
                vscode.postMessage({
                    command: 'run-command',
                    name: 'end-sandbox'                 
                });
            });
            </script>
        `;
        return html + script;
    }
}
