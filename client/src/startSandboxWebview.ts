import * as vscode from 'vscode';


function getWebviewOptions(extensionUri: vscode.Uri): vscode.WebviewOptions {
	return {
		// Enable javascript in the webview
		enableScripts: true,

		// And restrict the webview to only loading content from our extension's `media` directory.
		localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
	};
}

/**
 * Manages cat coding webview panels
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
    private _space: string;
    private _inputs: Array<string>;
	private _disposables: vscode.Disposable[] = [];

	public static createOrShow(extensionUri: vscode.Uri, bpname:string, space:string, inputs:Array<string>) {
        const column = vscode.window.activeTextEditor
			? vscode.window.activeTextEditor.viewColumn
			: undefined;

		// If we already have a panel, show it.
		if (SandboxStartPanel.currentPanel) {
			SandboxStartPanel.currentPanel.updatePanel(bpname, space, inputs);
            SandboxStartPanel.currentPanel._panel.reveal(column);
            return;
		}

		// Otherwise, create a new panel.
		const panel = vscode.window.createWebviewPanel(
			SandboxStartPanel.viewType,
			'Start Sandbox',
			column || vscode.ViewColumn.One,
			getWebviewOptions(extensionUri),
		);

		SandboxStartPanel.currentPanel = new SandboxStartPanel(panel, extensionUri, bpname, space, inputs);
	}

	private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, bpname:string, space:string, inputs:Array<string>) {
		this._panel = panel;
		this._extensionUri = extensionUri;
        this._bpname = decodeURI(bpname);
        this._space = space;
        this._inputs = inputs;

		// Set the webview's initial html content
		this._update();

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
                        if (message.name == 'start-sandbox') {
                            vscode.commands.executeCommand('start_torque_sandbox', bpname, message.duration, message.inputs)
                        }
                        return;
				}
			},
			null,
			this._disposables
		);
	}

    public updatePanel(bpname:string, space:string, inputs:Array<string>) {
        this._bpname = decodeURI(bpname);
        this._space = space;
        this._inputs = inputs;

		// Set the webview's initial html content
		this._update();
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

	private _update() {
		const webview = this._panel.webview;

		this._panel.title = 'Start Sandbox';
		this._panel.webview.html = this._getHtmlForWebview(webview);
	}

	private _getHtmlForWebview(webview: vscode.Webview) {
		// Local path to main script run in the webview
		// const scriptPathOnDisk = vscode.Uri.joinPath(this._extensionUri, 'media', 'main.js');

		// And the uri we use to load this script in the webview
		// const scriptUri = webview.asWebviewUri(scriptPathOnDisk);

		// Local path to css styles
		// const styleResetPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'reset.css');
		const stylesPathMainPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'vscode.css');

		// Uri to load styles into webview
		// const stylesResetUri = webview.asWebviewUri(styleResetPath);
		const stylesMainUri = webview.asWebviewUri(stylesPathMainPath);

		// Use a nonce to only allow specific scripts to be run
		const nonce = getNonce();
		const nonce2 = getNonce();
        var inputsHtml = "<table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        inputsHtml += "<tr><td width='180px'>" + "Duration (minutes) *" + "</td><td>" + "<input type='number' id='duration' value='30' min='10' max='3600'></td></tr>";
        var postMessageProperties = "duration: document.getElementById('duration').value, inputs: {";        
        for (var i=0; i<this._inputs.length; i++)
        {
            inputsHtml += "<tr><td>" + this._inputs[i]['name'] + (!this._inputs[i]['optional']? ' *': '') + "</td><td>" + "<input type=" + (this._inputs[i]['display_style']=='masked'?'password':'text') + " id='" + this._inputs[i]['name'] + "' value='" + (this._inputs[i]['default_value'] ? this._inputs[i]['default_value'] : '') + "'></td></tr>";
            postMessageProperties += this._inputs[i]['name'] + ": document.getElementById('" + this._inputs[i]['name'] + "').value,";
        }
        postMessageProperties += "}"
        inputsHtml += "<tr><td width='180px'><br/><input type='button' id='start-btn' value='Start'></td><td></td></tr>"
        inputsHtml += "</table>"
        
		return `<!DOCTYPE html>
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

				<title>Launch a New Sandbox</title>
			</head>
			<body>
                <br/>
				<h2>Launch a New Sandbox</h2>
				<h3>Blueprint: ${this._bpname}</h3>

				${inputsHtml}
                    
                
			</body>
            <script nonce="${nonce}">
            document.getElementById("start-btn").addEventListener("click", function() {
                startSandbox();
            });
            function startSandbox() {
                const vscode = acquireVsCodeApi();
                
                vscode.postMessage({
                    command: 'run-command',
                    name: 'start-sandbox',
                    ${postMessageProperties}                    
                });
                
            }
            </script>
			</html>`;
	}
}

function getNonce() {
	let text = '';
	const possible = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
	for (let i = 0; i < 32; i++) {
		text += possible.charAt(Math.floor(Math.random() * possible.length));
	}
	return text;
}