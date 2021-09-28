import * as vscode from 'vscode';
import * as path from 'path';
import { resourceUsage } from 'process';

export class SandboxesProvider implements vscode.TreeDataProvider<Sandbox> {

	private _onDidChangeTreeData: vscode.EventEmitter<Sandbox | undefined | void> = new vscode.EventEmitter<Sandbox | undefined | void>();
	readonly onDidChangeTreeData: vscode.Event<Sandbox | undefined | void> = this._onDidChangeTreeData.event;

	constructor() {
        console.log("before get connections");
	}

	refresh(): void {
		this._onDidChangeTreeData.fire();
	}

	getTreeItem(element: Sandbox): vscode.TreeItem {
		return element;
	}

	getChildren(element?: Sandbox): Thenable<Sandbox[]> {
		return new Promise(async (resolve) => {
			const default_profile = vscode.workspace.getConfiguration('torque').get<string>("default_profile", "");
			var results = []
      
			if (element) {
				console.log("element")
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
							for (var sb of result)
								sandboxes.push(new Sandbox(
									sb['name'],
									vscode.TreeItemCollapsibleState.None,
									sb['id'],
									sb['blueprint_name'])
								)
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

export class Sandbox extends vscode.TreeItem {
	constructor(
		public readonly label: string,
		public readonly collapsibleState: vscode.TreeItemCollapsibleState,
		public id: string,
		public blueprint_name: string,
		public readonly command?: vscode.Command,

	) {
		super(label, collapsibleState);

		this.tooltip = `Originated from the blueprint '${this.blueprint_name}'`;
		this.description = this.id;
	}

	iconPath = {
		light: path.join(__filename, '..', '..', 'resources', 'light', 'dependency.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'dependency.svg')
	};

	contextValue = 'dependency';
}
