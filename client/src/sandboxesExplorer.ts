import { setTimeout } from 'timers';
import * as vscode from 'vscode';
import { Sandbox } from './models';
import { ProfilesManager } from './profilesManager';

export class SandboxesProvider implements vscode.TreeDataProvider<Sandbox> {
	private _onDidChangeTreeData: vscode.EventEmitter<Sandbox | undefined | void> = new vscode.EventEmitter<Sandbox | undefined | void>();
	readonly onDidChangeTreeData: vscode.Event<Sandbox | undefined | void> = this._onDidChangeTreeData.event;
	private pendingRefresh?: NodeJS.Timeout;
	private firstLoad = true;

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

	async endEnvironment(sandbox: Sandbox): Promise<any> {
		return vscode.window.showInformationMessage(
            "Ending an environment permanently removes its resources from the cloud. Are you sure you want to end this environment?",
            ...["No", "Yes"]
        )
        .then((answer) => {
            if (answer === "Yes") {
				vscode.window.showInformationMessage(`Ending the environment ${sandbox.id}...`)
				vscode.commands.executeCommand('end_sandbox', sandbox.id);
				vscode.window.showInformationMessage('End request sent');
				this.refreshDelayed(30);
            }
        });

		
    }

	async getEnvDetails(sb: any): Promise<void> {
		vscode.commands.executeCommand('extension.showSandboxDetails', sb)
	}
	
	getChildren(element?: Sandbox): Thenable<Sandbox[]> {
		return new Promise(async (resolve) => {
			if (!element && this.firstLoad) {
				this.firstLoad = false;
				return resolve([])
			}

			if (element) {
				return resolve([]);
			}
			else {
				const active_profile = (ProfilesManager.getInstance().getActive() === undefined) ? "" : ProfilesManager.getInstance().getActive().label
				const results = []
      
				if (active_profile === "") {
					vscode.window.showInformationMessage('No default profile is defined');
					results.push(this.getLoginTreeItem())
					return resolve(results);
				} else {
					const sandboxes = []
					
					vscode.commands.executeCommand('list_sandboxes')
					.then(async (result:Array<string>) => {
						if (result.length > 0) {
							for (let sb of result) {
								sandboxes.push(new Sandbox(
									sb['name'],
									vscode.TreeItemCollapsibleState.None,
									sb['id'],
									sb['blueprint_name'],
									{
										command: 'environmentsExplorerView.getEnvDetails',
										title: 'Environment Details',
										arguments: [sb] 
									}
									)
								)
							}
							return resolve(sandboxes)
						}
						else return resolve([])
					})
					//return resolve(sandboxes)
				}
			}
		});
	}

	private getLoginTreeItem() : vscode.TreeItem {
		const message = new vscode.TreeItem("Login to Torque", vscode.TreeItemCollapsibleState.None)
		message.command = {command: 'profilesView.addProfile', 'title': 'Login'}
		message.tooltip = "Currently you don't have any profiles configured. Login to Torque in order to create the first profile"
		return message
	}
}

