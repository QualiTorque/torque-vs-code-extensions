import * as vscode from 'vscode';
import { getNonce } from './utils'
const path = require('path')


function getWebviewOptions(extensionUri: vscode.Uri): vscode.WebviewOptions {
	return {
		// Enable javascript in the webview
		enableScripts: true,

		// And restrict the webview to only loading content from our extension's `media` directory.
		localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
	};
}

/**
 * Manages start sandbox webview panels
 */
export class SandboxStartPanel {
	/**
	 * Track the currently panel. Only allow a single panel to exist at a time.
	 */
	public static currentPanel: SandboxStartPanel | undefined;

	public static readonly viewType = 'startSandbox';

	private readonly _panel: vscode.WebviewPanel;
	private readonly _extensionUri: vscode.Uri;

    private _bpname: string;
	private _blueprintDetails: string;
	private _disposables: vscode.Disposable[] = [];
	private _sourceType: string;
	private readonly _branch: string;

	public static createOrShow(extensionUri: vscode.Uri, bpname:string, inputs:Array<string>, branch: string, sourceType: string) {
		const column = vscode.window.activeTextEditor
			? vscode.window.activeTextEditor.viewColumn
			: undefined;

		// If we already have a panel, show it.
		if (SandboxStartPanel.currentPanel) {
			SandboxStartPanel.currentPanel.updatePanel(bpname, inputs, sourceType);
            SandboxStartPanel.currentPanel._panel.reveal(column);
            return;
		}

		// Otherwise, create a new panel.
		const panel = vscode.window.createWebviewPanel(
			SandboxStartPanel.viewType,
			'Start Environment',
			column || vscode.ViewColumn.One,
			getWebviewOptions(extensionUri),
		);
		SandboxStartPanel.currentPanel = new SandboxStartPanel(panel, extensionUri, bpname, branch, sourceType);
	}

	private startSandbox(bpname: string, sandbox_name: string, duration: number, inputs:object, branch:string, sourceType:string) {
		let inputsString = this._compose_comma_separated_string(inputs);

		vscode.commands.executeCommand('start_torque_sandbox', bpname, sandbox_name, duration, inputsString, branch, sourceType)
		.then(async (result:Array<string>) => {
			vscode.commands.executeCommand('environmentsExplorerView.refreshEntry')
			this._panel.dispose();
		})
	}

	private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, bpname:string, branch: string, sourceType: string) {
		this._panel = panel;
		this._extensionUri = extensionUri;
        this._bpname = decodeURI(bpname);
		this._branch = branch;
		this._sourceType = sourceType;
		this._blueprintDetails = null;

		// Set the webview's initial html content
		this._update();
		this.reloadBlueprintDetails();		

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
						if (message.name == 'reload-blueprint') {
                            this.reloadBlueprintDetails();
						}
                        else if (message.name == 'start-sandbox') {
                            this.startSandbox(this._bpname, message.sandbox_name, message.duration, message.inputs, this._branch, this._sourceType);
						}
                        return;
				}
			},
			null,
			this._disposables
		);
	}

	private async reloadBlueprintDetails() {
		return vscode.window.withProgress({location: vscode.ProgressLocation.Notification}, (progress): Promise<string> => {
            return new Promise<string>(async (resolve) => {
                progress.report({ message: "Loading blueprint details" });
                await vscode.commands.executeCommand('get_blueprint', this._bpname, this._sourceType)
                .then(async (result:string) => {
                    if (result.length > 0)
                        this._blueprintDetails = result;
                        this._update();
                })
                resolve("")
            })
        })
	}

    public updatePanel(bpname:string, inputs:Array<string>, sourceType: string) {
        this._bpname = decodeURI(bpname);
		this._blueprintDetails = null;
		this._sourceType = sourceType;
		// Set the webview's initial html content
		this._update();
		this.reloadBlueprintDetails();
    }

	public dispose() {
		SandboxStartPanel.currentPanel = undefined;

		// Clean up our resources
		this._panel.dispose();

		while (this._disposables.length) {
			const x = this._disposables.pop();
			if (x) {
				x.dispose();
			}
		}
	}
	private _compose_comma_separated_string(mapContainer: object) : string{
		let resultString = "";
		for (const [key, value] of Object.entries(mapContainer))
		{
			if (value!='')
				resultString += `${key}=${value},`
			// else
			// 	resultString += `${key}="",`
		}
		resultString.trimEnd;
		if (resultString.length > 2) 
			resultString = resultString.substring(0, resultString.length - 1)
		
		return resultString
	}

	private _update() {
		const webview = this._panel.webview;

		this._panel.title = 'Start Environment';
		this._panel.webview.html = this._getHtmlForWebview(webview);
	}

    private _isEmpty(obj) {
        for (let j in obj) { return false }
        return true;
    }

	private _getHtmlForWebview(webview: vscode.Webview) {
		const default_duration = vscode.workspace.getConfiguration('torque').get<number>("defaultSandboxDuration", 120);
		const stylesPathMainPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'vscode.css');

		const stylesMainUri = webview.asWebviewUri(stylesPathMainPath);
		const nonce = getNonce();

		let cleanName = this._bpname;
		if (cleanName.endsWith('.yaml'))
			cleanName = cleanName.replace('.yaml', '').split('/').slice(-1)[0]	
		if (cleanName.startsWith('[Sample]'))
			cleanName = cleanName.replace('[Sample]','');

		if (!this._blueprintDetails) {
			return `
				<body>
					<div style="vertical-align: top; display: inline-block; margin-top: 5px">
						<h2>${cleanName}</h2>
						<br/>
						</div>
						<div style="vertical-align: top;">
						<h4>Loading details...</h4>
					</div>
				</body>`;
		}
		
		let generalHtml = "<table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        generalHtml += "<tr><td width='180px'>" + "Name" + "</td><td>" + "<input type='text' id='sandbox_name' value='" + cleanName + "'></td></tr>";
        generalHtml += "<tr><td width='180px'>" + "Duration (minutes) *" + "</td><td>" + "<input type='number' id='duration' value='" + default_duration.toString() + "' min='10' max='3600'></td></tr>";
        generalHtml += "</table>";

		let blueprintJson = JSON.parse(this._blueprintDetails);

		// spec2 check
		if ("details" in blueprintJson)
			blueprintJson = blueprintJson['details'];

		let inputsHtml = "";
		let postMessageProperties = "sandbox_name: document.getElementById('sandbox_name').value, duration: document.getElementById('duration').value";
		let inputs = blueprintJson['inputs'];
		let inputs_size = inputs.length;

		if (inputs_size > 0) {
			// let inputs = blueprintJson['inputs'];
			inputsHtml = "<b>Inputs</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
            postMessageProperties += ", inputs: {";        
            for (let i = 0; i < inputs_size; i++){
                inputsHtml += ("<tr><td width='180px'>" 
							+ inputs[i]['name'] + (!inputs[i]['optional']? ' *': '')
							+ "</td><td>" + "<input type=" + (inputs[i]['display_style']=='masked'?'password':'text') + " id='"
							+ inputs[i]['name'] + "' value='" + (inputs[i]['default_value'] ? inputs[i]['default_value'] : '')
							+ "'></td></tr>");
                postMessageProperties += `"${inputs[i]['name']}": document.getElementById('${inputs[i]['name']}').value,`;
            }
            inputsHtml += "</table>";
            postMessageProperties += "}";            
        }
        else
            postMessageProperties += ", inputs: {}";


        let startHtml = "<br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        startHtml += ("<tr><td width='180px'><input type='button' id='start-btn' value='Start'></td>"
						+ "<td width='180px'><input type='button' id='reload-btn' value='Refresh'></td></tr>");
        startHtml += "</table>";
        
		// Use a nonce to only allow specific scripts to be run
		
		let html = `<!DOCTYPE html>
			<html lang="en">
			<head>
				<meta charset="UTF-8">

				<!--
					Use a content security policy to only allow loading images from https or from our extension directory,
					and only allow scripts that have a specific nonce.
				-->
				<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; img-src ${webview.cspSource} https:; script-src 'nonce-${nonce}';">

				<meta name="viewport" content="width=device-width, initial-scale=1.0">

				<link href="${stylesMainUri}" rel="stylesheet">

				<title>Launch a New Environment</title>
			</head>
			<body>
                <br/>
				<h2>Launch a New Environment</h2>
				<h3>Blueprint: ${cleanName}</h3>
                <br/>
				${generalHtml}
                <br/>
				${inputsHtml}
                ${startHtml}
			</body>
            <script nonce="${nonce}">
                const vscode = acquireVsCodeApi();
				document.getElementById("reload-btn").addEventListener("click", function() {
					vscode.postMessage({
						command: 'run-command',
						name: 'reload-blueprint'                 
					});
				});
                document.getElementById("start-btn").addEventListener("click", function() {
					this.disabled = true;
					startSandbox();
                }, { once: true });
                function startSandbox() {                
                    vscode.postMessage({
                        command: 'run-command',
                        name: 'start-sandbox',
                        ${postMessageProperties}                    
                    });
                }
            </script>
			</html>`;
        return html;
	}
}
