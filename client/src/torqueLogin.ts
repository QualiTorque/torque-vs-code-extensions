import * as vscode from 'vscode'
import { loginFormHtml } from './loginFormHtml'
import { ProfilesProvider } from './profiles';

export class LoginCommand extends vscode.TreeItem {
    constructor(
        public readonly label : string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,

    ) {
        super(label,collapsibleState)
        this.tooltip = this.label
    }

	contextValue = 'dependency';

}
export function torqueLogin(profilesTree: ProfilesProvider, listener?: (message: any) => Promise<void>): vscode.WebviewPanel {
    const panel = vscode.window.createWebviewPanel(
        'html',
        'Login To Torque',
        vscode.ViewColumn.Active,
        {
            retainContextWhenHidden: true,
            enableScripts: true,
        }
    )
    panel.webview.html = loginFormHtml

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
