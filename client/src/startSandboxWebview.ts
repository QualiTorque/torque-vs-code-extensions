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
    // private _space: string;
    private _inputs: Array<string>;
    private _artifacts: object;
	private _disposables: vscode.Disposable[] = [];

	// public static createOrShow(extensionUri: vscode.Uri, bpname:string, space:string, inputs:Array<string>, artifacts: object) {
	public static createOrShow(extensionUri: vscode.Uri, bpname:string, inputs:Array<string>, artifacts: object) {
		const column = vscode.window.activeTextEditor
			? vscode.window.activeTextEditor.viewColumn
			: undefined;

		// If we already have a panel, show it.
		if (SandboxStartPanel.currentPanel) {
			// SandboxStartPanel.currentPanel.updatePanel(bpname, space, inputs, artifacts);
			SandboxStartPanel.currentPanel.updatePanel(bpname, inputs, artifacts);
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
		// SandboxStartPanel.currentPanel = new SandboxStartPanel(panel, extensionUri, bpname, space, inputs, artifacts);
		SandboxStartPanel.currentPanel = new SandboxStartPanel(panel, extensionUri, bpname, inputs, artifacts);
	}

	private async startSandbox(bpname: string, sandbox_name: string, duration: number, inputs:object, artifacts:object) {
		await vscode.commands.executeCommand('start_torque_sandbox', bpname, sandbox_name, duration, inputs, artifacts)
		.then(async (result:Array<string>) => {
			vscode.commands.executeCommand('sandboxesExplorerView.refreshEntry')
		})
	}

	// private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, bpname:string, space:string, inputs:Array<string>, artifacts: object) {
	private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri, bpname:string, inputs:Array<string>, artifacts: object) {
		this._panel = panel;
		this._extensionUri = extensionUri;
        this._bpname = decodeURI(bpname);
        // this._space = space;
        this._inputs = inputs;
        this._artifacts = artifacts;

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
                            this.startSandbox(this._bpname, message.sandbox_name, message.duration, message.inputs, message.artifacts);
                        }
                        return;
				}
			},
			null,
			this._disposables
		);
	}

    // public updatePanel(bpname:string, space:string, inputs:Array<string>, artifacts: object) {
	public updatePanel(bpname:string, inputs:Array<string>, artifacts: object) {
        this._bpname = decodeURI(bpname);
        // this._space = space;
        this._inputs = inputs;
        this._artifacts = artifacts;

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

    private _isEmpty(obj) {
        for (var j in obj) { return false }
        return true;
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
		var cleanName = this._bpname;
		if (cleanName.endsWith('.yaml'))
		{
			cleanName = cleanName.replace('.yaml', '').split(path.sep).slice(-1)[0]
		}
		const nonce = getNonce();
		var generalHtml = "<table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        generalHtml += "<tr><td width='180px'>" + "Name" + "</td><td>" + "<input type='text' id='sandbox_name' value='" + cleanName + "'></td></tr>";
        generalHtml += "<tr><td width='180px'>" + "Duration (minutes) *" + "</td><td>" + "<input type='number' id='duration' value='30' min='10' max='3600'></td></tr>";
        generalHtml += "</table>";

        if (this._inputs.length > 0) {
            var inputsHtml = "<b>Inputs</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
            var postMessageProperties = "sandbox_name: document.getElementById('sandbox_name').value, duration: document.getElementById('duration').value, inputs: {";        
            for (var i=0; i<this._inputs.length; i++)
            {
                inputsHtml += "<tr><td width='180px'>" + this._inputs[i]['name'] + (!this._inputs[i]['optional']? ' *': '') + "</td><td>" + "<input type=" + (this._inputs[i]['display_style']=='masked'?'password':'text') + " id='" + this._inputs[i]['name'] + "' value='" + (this._inputs[i]['default_value'] ? this._inputs[i]['default_value'] : '') + "'></td></tr>";
                postMessageProperties += `"${this._inputs[i]['name']}": document.getElementById('${this._inputs[i]['name']}').value,`;
            }
            inputsHtml += "</table>";
            postMessageProperties += "}";            
        }
        else {
            var inputsHtml = "";
            var postMessageProperties = "duration: document.getElementById('duration').value, inputs: {}";   
        }

        if (!this._isEmpty(this._artifacts)) {
            var artifactsHtml = "<b>Artifacts</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
            postMessageProperties += ", artifacts: {";        
            for (const [key, value] of Object.entries(this._artifacts)) {
                artifactsHtml += "<tr><td width='180px'>" + key + ' *' + "</td><td>" + "<input type='text' id='art_" + key + "' value='" + (value ? value : '') + "'></td></tr>";
                postMessageProperties += `"${key}": document.getElementById('art_${key}').value,`;
            }
            artifactsHtml += "</table>";
            postMessageProperties += "}";
            if (this._inputs.length > 0)
                artifactsHtml = "<br/>" + artifactsHtml;
        }
        else {
            var artifactsHtml = "";
            postMessageProperties += ", artifacts: {}";
        }
        
        var startHtml = "<br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        startHtml += "<tr><td width='180px'><input type='button' id='start-btn' value='Start'></td><td></td></tr>";
        startHtml += "</table>";
        
		var html = `<!DOCTYPE html>
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
                <br/>
				${generalHtml}
                <br/>
				${inputsHtml}
                ${artifactsHtml}
                ${startHtml}
			</body>
            <script nonce="${nonce}">
                const vscode = acquireVsCodeApi();
                document.getElementById("start-btn").addEventListener("click", function() {
                    startSandbox();
                });
                function startSandbox() {                
                    vscode.postMessage({
                        command: 'run-command',
                        name: 'start-sandbox',
                        ${postMessageProperties}                    
                    });
                }
            </script>
			</html>`;


		//test sandbox details html
		// var title = 'aaaaaaaa';
		// var blueprint_name = 'blueprint name'
		// var sandbox_status = "Active";
		// var create_time = '2021-09-28T20:34:03.993243+00:00'
		// var scheduled_end_time = '2021-09-28T20:34:03.993243+00:00'
		// var sandbox_url = 'https://trial-dc588bf8.qtorque.io/Trial/sandboxes/nc6373wln300z1'
		// var inputs = [{'name': 'input1', 'value': 'value1'}, {'name': 'input2', 'value': 'value2'}]
		// var artifacts = {}
		// var shortcuts = [{'name': 'app1', 'shortcuts': ['http://sandb-MainA-LFA6RZ04WIWO-1717599593.us-west-2.elb.amazonaws.com:3000']}] //will be inside the applications part

		// var generalHtml = "<table width='50%' border='0' cellpadding='1' cellspacing='1'>";
	
        // generalHtml += "<tr><td width='180px'>" + "Status" + "</td><td>" + sandbox_status + "</td></tr>";
        // generalHtml += "<tr><td width='180px'>" + "Launched at" + "</td><td>" + create_time + "</td></tr>";
        // generalHtml += "<tr><td width='180px'>" + "End time" + "</td><td>" + scheduled_end_time + "</td></tr>";
		// if (sandbox_url) {
		// 	generalHtml += "<tr><td width='180px'><a href='" + sandbox_url +"' target='_blank'/>" + "Open in Torque" + "</td><td></td></tr>";
		// }
        // generalHtml += "</table>";

		// if (shortcuts.length > 0) {
        //     var shortcutsHtml = "<b>Quick Links</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        //     for (var i=0; i<shortcuts.length; i++)
        //     {
        //         shortcutsHtml += "<tr><td width='180px'>" + shortcuts[i]['name'] + "</td><td><a href='" + shortcuts[i]['shortcuts'][0] + "' target='_blank'>" + shortcuts[i]['shortcuts'][0] + "</a></td><td></tr>";
        //     }
        //     shortcutsHtml += "</table>";            
        // }
        // else {
        //     var shortcutsHtml = "";
        // }

		// if (inputs.length > 0) {
        //     var inputsHtml = "<b>Inputs</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        //     for (var i=0; i<inputs.length; i++)
        //     {
        //         inputsHtml += "<tr><td width='180px'>" + inputs[i]['name'] + "</td><td>" + inputs[i]['value'] + "</td><td></tr>";
        //     }
        //     inputsHtml += "</table>";            
        // }
        // else {
        //     var inputsHtml = "";
        // }

        // if (!this._isEmpty(artifacts)) {
        //     var artifactsHtml = "<b>Artifacts</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        //     for (const [key, value] of Object.entries(artifacts)) {
        //         artifactsHtml += "<tr><td width='180px'>" + key  + "</td><td>" + value + "</td></tr>";
        //     }
        //     artifactsHtml += "</table>";
        //     if (this._inputs.length > 0)
        //         artifactsHtml = "<br/>" + artifactsHtml;
        // }
        // else {
        //     var artifactsHtml = "";
        // }	

		// html = `<!DOCTYPE html>
		// 	<html lang="en">
		// 	<head>
		// 		<meta charset="UTF-8">

		// 		<!--
		// 			Use a content security policy to only allow loading images from https or from our extension directory,
		// 			and only allow scripts that have a specific nonce.
		// 		-->
		// 		<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${webview.cspSource}; img-src ${webview.cspSource} https:; script-src 'nonce-${nonce}';">

		// 		<meta name="viewport" content="width=device-width, initial-scale=1.0">

		// 		<link href="${stylesMainUri}" rel="stylesheet">

		// 		<title>${title}</title>
		// 	</head>
		// 	<body>
        //         <br/>
		// 		<h2>${title}</h2>
		// 		<h3>Blueprint: ${blueprint_name}</h3>
        //         <br/>
		// 		${generalHtml}
        //         <br/>
		// 		${shortcutsHtml}
		// 		${inputsHtml}
        //         ${artifactsHtml}                
		// 	</body>
            
		// 	</html>`;




        return html;
	}
}

