import * as vscode from 'vscode'
import { Sandbox } from './sandboxesExplorer';
import { getNonce } from './utils'

export function sandboxDetailsPanel(extensionUri: vscode.Uri, sandbox: any, details: any): vscode.WebviewPanel {
    const panel = vscode.window.createWebviewPanel(
        'html',
        'Sandbox details',
        vscode.ViewColumn.Active,
        {
            retainContextWhenHidden: true,
            enableScripts: true,
            localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
        }
    )
    const stylesPathMainPath = vscode.Uri.joinPath(extensionUri, 'media', 'vscode.css');
    const stylesMainUri = panel.webview.asWebviewUri(stylesPathMainPath);
    const nonce = getNonce();

    const htmlHeader = `<!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">

        <!--
            Use a content security policy to only allow loading images from https or from our extension directory,
            and only allow scripts that have a specific nonce.
        -->
        <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${panel.webview.cspSource}; img-src ${panel.webview.cspSource} https:; script-src 'nonce-${nonce}';">

        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <link href="${stylesMainUri}" rel="stylesheet">

        <title>${sandbox.name}</title>
    </head>`

    // const htmlBody = getMainBody(sandbox)
    const htmlBody = getBaseInfo(sandbox, details)

    panel.webview.html = htmlHeader + htmlBody;
    return panel;
}

function isEmpty(obj) {
    for (var j in obj) { return false }
    return true;
}

function getBaseInfo(sandbox: any, details: any) {
    var generalHtml = "<table width='50%' border='0' cellpadding='1' cellspacing='1'>";

    const profile = vscode.workspace.getConfiguration('torque').get<string>("default_profile", "");
    generalHtml += "<tr><td width='180px'>" + "ID" + "</td><td>" + sandbox.id + "</td></tr>";
    generalHtml += "<tr><td width='180px'>" + "Status" + "</td><td>" + details.get('status') + "</td></tr>";

    // if (sandbox_url) {
    //     generalHtml += "<tr><td width='180px'><a href='" + sandbox_url +"' target='_blank'/>" + "Open in Torque" + "</td><td></td></tr>";
    // }

    generalHtml += "</table>";

    
    const html = `
    	<body>
            <br/>
    		<h2>${sandbox.name}</h2>
    		<h3>Blueprint: ${sandbox.blueprint_name}</h3>
            <br/>
    		${generalHtml}
            <br/>              
    	</body>
        
    	</html>`;
    return html;
}
    
function getMainBody(sandbox: Sandbox) {
    //test sandbox details html
    var title = 'aaaaaaaa';
    var blueprint_name = 'blueprint name'
    var sandbox_status = "Active";
    var create_time = '2021-09-28T20:34:03.993243+00:00'
    var scheduled_end_time = '2021-09-28T20:34:03.993243+00:00'
    var sandbox_url = 'https://trial-dc588bf8.qtorque.io/Trial/sandboxes/nc6373wln300z1'
    var inputs = [{'name': 'input1', 'value': 'value1'}, {'name': 'input2', 'value': 'value2'}]
    var artifacts = {}
    var shortcuts = [{'name': 'app1', 'shortcuts': ['http://sandb-MainA-LFA6RZ04WIWO-1717599593.us-west-2.elb.amazonaws.com:3000']}] //will be inside the applications part

    var generalHtml = "<table width='50%' border='0' cellpadding='1' cellspacing='1'>";

    generalHtml += "<tr><td width='180px'>" + "Status" + "</td><td>" + sandbox_status + "</td></tr>";
    generalHtml += "<tr><td width='180px'>" + "Launched at" + "</td><td>" + create_time + "</td></tr>";
    generalHtml += "<tr><td width='180px'>" + "End time" + "</td><td>" + scheduled_end_time + "</td></tr>";
    if (sandbox_url) {
    	generalHtml += "<tr><td width='180px'><a href='" + sandbox_url +"' target='_blank'/>" + "Open in Torque" + "</td><td></td></tr>";
    }
    generalHtml += "</table>";

    if (shortcuts.length > 0) {
        var shortcutsHtml = "<b>Quick Links</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        for (var i=0; i<shortcuts.length; i++)
        {
            shortcutsHtml += "<tr><td width='180px'>" + shortcuts[i]['name'] + "</td><td><a href='" + shortcuts[i]['shortcuts'][0] + "' target='_blank'>" + shortcuts[i]['shortcuts'][0] + "</a></td><td></tr>";
        }
        shortcutsHtml += "</table>";            
    }
    else {
        var shortcutsHtml = "";
    }

    if (inputs.length > 0) {
        var inputsHtml = "<b>Inputs</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        for (var i=0; i<inputs.length; i++)
        {
            inputsHtml += "<tr><td width='180px'>" + inputs[i]['name'] + "</td><td>" + inputs[i]['value'] + "</td><td></tr>";
        }
        inputsHtml += "</table>";            
    }
    else {
        var inputsHtml = "";
    }

    if (!isEmpty(artifacts)) {
        var artifactsHtml = "<b>Artifacts</b><br/><table width='50%' border='0' cellpadding='1' cellspacing='1'>";
        for (const [key, value] of Object.entries(artifacts)) {
            artifactsHtml += "<tr><td width='180px'>" + key  + "</td><td>" + value + "</td></tr>";
        }
        artifactsHtml += "</table>";
        if (this._inputs.length > 0)
            artifactsHtml = "<br/>" + artifactsHtml;
    }
    else {
        var artifactsHtml = "";
    }	

    const html = `
    	<body>
            <br/>
    		<h2>${title}</h2>
    		<h3>Blueprint: ${blueprint_name}</h3>
            <br/>
    		${generalHtml}
            <br/>
    		${shortcutsHtml}
    		${inputsHtml}
            ${artifactsHtml}                
    	</body>
        
    	</html>`;
        return html;
}
