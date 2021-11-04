import * as vscode from 'vscode'
import { loginFormHtml } from './loginFormHtml'
import { ProfilesProvider } from './profilesExplorer';
import { getNonce } from './utils'

export function torqueLogin(extensionUri: vscode.Uri, profilesTree: ProfilesProvider): vscode.WebviewPanel {
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

    let html = loginFormHtml;
    let head = `<link href="${stylesMainUri}" rel="stylesheet">`;

    html = html.replace('{{HEAD_BLOCK}}', head);

    panel.webview.html = html;

    panel.webview.onDidReceiveMessage(
        message => {
            switch (message.command) {
                case 'alert':
                    vscode.window.showErrorMessage(message.text);
                    return;
                case 'login':
                    if (message.profile && message.account && message.space && ((message.email && message.password) || message.token)) {
                        vscode.commands.executeCommand('torque_login', message).then((result: string) => 
                        {
                            if (result) {
                                vscode.window.showErrorMessage("Unable to login, please check the provided information and try again");
                            } else {
                                vscode.window.showInformationMessage("Profile added.")
                                panel.dispose()
                            }
                        });
                        profilesTree.refresh();
                    }
                    else {
                        vscode.window.showErrorMessage("Please provide all the required fields together with one credentials option (Email+Password or Token).");
                    }

                    return;
            }
        },
        undefined,
        null
    );

    return panel
}
