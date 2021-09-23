import * as vscode from 'vscode'
import { loginFormHtml } from './loginFormHtml'
import { ProfilesProvider } from './profiles';
import { getNonce } from './utils'

// export class LoginCommand extends vscode.TreeItem {
//     constructor(
//         public readonly label : string,
//         public readonly collapsibleState: vscode.TreeItemCollapsibleState,

//     ) {
//         super(label,collapsibleState)
//         this.tooltip = this.label
//     }

// 	contextValue = 'dependency';

// }
export function torqueLogin(extensionUri: vscode.Uri, profilesTree: ProfilesProvider, listener?: (message: any) => Promise<void>): vscode.WebviewPanel {
    const panel = vscode.window.createWebviewPanel(
        'html',
        'Login to Torque',
        vscode.ViewColumn.Active,
        {
            retainContextWhenHidden: true,
            enableScripts: true,
            localResourceRoots: [vscode.Uri.joinPath(extensionUri, 'media')]
        }
    )

    // Local path to main script run in the webview
    // const scriptPathOnDisk = vscode.Uri.joinPath(this._extensionUri, 'media', 'main.js');

    // And the uri we use to load this script in the webview
    // const scriptUri = webview.asWebviewUri(scriptPathOnDisk);

    // Local path to css styles
    // const styleResetPath = vscode.Uri.joinPath(this._extensionUri, 'media', 'reset.css');
    const stylesPathMainPath = vscode.Uri.joinPath(extensionUri, 'media', 'vscode.css');

    // Uri to load styles into webview
    // const stylesResetUri = webview.asWebviewUri(styleResetPath);
    const stylesMainUri = panel.webview.asWebviewUri(stylesPathMainPath);

    // Use a nonce to only allow specific scripts to be run
    const nonce = getNonce();

    var html = loginFormHtml
    var head = `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src ${panel.webview.cspSource}; img-src ${panel.webview.cspSource} https:; script-src 'nonce-${nonce}';">
                <link href="${stylesMainUri}" rel="stylesheet">`;
    head = `<link href="${stylesMainUri}" rel="stylesheet">`;

    // var style = `.app { background-image: url()}`
    html = html.replace('{{HEAD_BLOCK}}', head)
    // html = html.replace('{{STYLE_BLOCK}}', style)

    panel.webview.html = html

    panel.webview.onDidReceiveMessage(
        message => {
            switch (message.command) {
                case 'alert':
                    vscode.window.showErrorMessage(message.text);
                    return;
                case 'login':
                    console.info(`Login...`)
                    vscode.commands.executeCommand('torque_login', message).then((result: string) => 
                    {
                        if (result) {
                            // panel.webview.postMessage({ statusCode: 'Failure', error: result })
                            vscode.window.showErrorMessage("Unable To login:\n" + result);
                        } else {
                            vscode.window.showInformationMessage("Profile has been added")
                            panel.dispose()
                        }
                    });
                    profilesTree.refresh();

                    return;
            }
        },
        undefined,
        null
    );

    return panel
}
