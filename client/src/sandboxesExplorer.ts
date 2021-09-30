import { setTimeout } from 'timers';
import * as vscode from 'vscode';
import { Sandbox } from './models';
import { ProfilesManager } from './profilesManager';

export class SandboxesProvider implements vscode.TreeDataProvider<Sandbox> {
	private _onDidChangeTreeData: vscode.EventEmitter<Sandbox | undefined | void> = new vscode.EventEmitter<Sandbox | undefined | void>();
	readonly onDidChangeTreeData: vscode.Event<Sandbox | undefined | void> = this._onDidChangeTreeData.event;
	private pendingRefresh?: NodeJS.Timeout;

	constructor() {}

	refresh(): void {
		this._onDidChangeTreeData.fire();
	}

	refreshDelayed(seconds: number): void {
		if (this.pendingRefresh !== undefined) {
		  clearTimeout(this.pendingRefresh);
		}
		this.pendingRefresh = setTimeout(() => {
		  this.pendingRefresh = undefined;
		  this.refresh();
		}, seconds * 1000);
	  }

	getTreeItem(element: Sandbox): vscode.TreeItem {
		return element;
	}

	async endSandbox(sandbox: Sandbox): Promise<any> {
		const default_profile = (ProfilesManager.getInstance().getActive() === undefined) ? "" : ProfilesManager.getInstance().getActive().label;
		vscode.window.showInformationMessage(`Ending the sandbox ${sandbox.id}...`)
		vscode.commands.executeCommand('end_sandbox', sandbox.id, default_profile );
		vscode.window.showInformationMessage('End request has been sent');
		this.refreshDelayed(30);
    }

	async getSandboxDetails(sb: any): Promise<void> {
		//let details = new Map();

		// await vscode.commands.executeCommand('get_sandbox', sb.id, profile )
		// .then(async (result:string) => {
		// 	if (result.length > 0)
		// 		details.set('status', result)
        // })

		vscode.commands.executeCommand('extension.showSandboxDetails', sb)
	}

	getChildren(element?: Sandbox): Thenable<Sandbox[]> {
		return new Promise(async (resolve) => {
			const default_profile = (ProfilesManager.getInstance().getActive() === undefined) ? "" : ProfilesManager.getInstance().getActive().label
			var results = []
      
			if (element) {
				return resolve(results);
			}
			else {
				if (default_profile === "") {
					vscode.window.showInformationMessage('No default profile is defined');
					results.push(this.getLoginTreeItem())
					return resolve(results);
				} else {
					var sandboxes = []
					await vscode.commands.executeCommand('list_sandboxes', default_profile)
					.then(async (result:Array<string>) => {
						if (result.length > 0) {
							for (var sb of result) {
								sandboxes.push(new Sandbox(
									sb['name'],
									vscode.TreeItemCollapsibleState.None,
									sb['id'],
									sb['blueprint_name'],
									{
										command: 'sandboxesExplorerView.getSandboxDetails',
										title: 'Sandbox Details',
										arguments: [sb] 
									}
									)
								)
							}
						}
					})
					resolve(sandboxes)
				}
			}
		});
	}

	private getLoginTreeItem() : vscode.TreeItem {
		var message = new vscode.TreeItem("Login to Torque", vscode.TreeItemCollapsibleState.None)
		message.command = {command: 'profilesView.addProfile', 'title': 'Login'}
		message.tooltip = "Currently you don't have any profiles confifured. Login to Torque in order to create the first profile"
		return message
	}
}

