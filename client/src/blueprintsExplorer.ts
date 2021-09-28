import * as vscode from 'vscode';
import * as path from 'path';

export class BlueprintsProvider implements vscode.TreeDataProvider<Blueprint> {

	private _onDidChangeTreeData: vscode.EventEmitter<Blueprint | undefined | void> = new vscode.EventEmitter<Blueprint | undefined | void>();
	readonly onDidChangeTreeData: vscode.Event<Blueprint | undefined | void> = this._onDidChangeTreeData.event;
    connections: Array<object>;

	constructor() {
        
	}

	refresh(): void {
		this._onDidChangeTreeData.fire();
	}

	getTreeItem(element: Blueprint): vscode.TreeItem {
		return element;
	}

	getChildren(element?: Blueprint): Thenable<Blueprint[]> {
		return new Promise(async (resolve) => {
			const default_profile = vscode.workspace.getConfiguration('torque').get<string>("default_profile", "");
			var results = []

			if (element) {
				console.log("element")
				return resolve(results);
			} else {
				if (default_profile === "") {
					vscode.window.showInformationMessage('No default profile is defined');
					results.push(this.getLoginTreeItem())
					return resolve(results);
				}
				else
					return resolve(this.getOnlineBlueprints(default_profile))
			}
		});
	}

	private getLoginTreeItem() : vscode.TreeItem {
		var message = new vscode.TreeItem("Login to Torque", vscode.TreeItemCollapsibleState.None)
		message.command = {command: 'profilesView.addProfile', 'title': 'Login'}
		message.tooltip = "Currently you don't have any profiles confifured. Login to Torque in order to create the first profile"
		return message
	}

	/**
	 * Given the path to package.json, read all its dependencies and devDependencies.
	 */
	private async getOnlineBlueprints(profile: string): Promise<Blueprint[]> {
		const bps = [];
		
		await vscode.commands.executeCommand('list_blueprints', profile)
		.then(async (result:string) => {
			if (result.length > 0) {
				const blueprintsJson = JSON.parse(result);

				const toBp = (blueprintName: string, description: string, is_sample: boolean, inputs: Array<string>, artifacts: string):
				Blueprint => {
					var cleanName = blueprintName;
					if (is_sample)
						cleanName = cleanName.replace('[Sample]', '')
					return new Blueprint(cleanName, description, vscode.TreeItemCollapsibleState.None, {
						command: 'extension.openReserveForm',
						title: '',
						arguments: [blueprintName, inputs, artifacts]
					});
				};

				for (var b=0; b<blueprintsJson.length; b++) {
					const bpj = blueprintsJson[b];
					if (bpj.errors.length==0 && bpj.enabled) { 
						var bp = toBp(bpj.blueprint_name, bpj.description, bpj.is_sample, bpj.inputs, bpj.artifacts);
						bps.push(bp);
					}
				}
			}	
		})
		return bps;
	}
}

export class Space extends vscode.TreeItem {

	constructor(
		public readonly label: string,
		public readonly collapsibleState: vscode.TreeItemCollapsibleState,
		
	) {
		super(label, collapsibleState);

		this.tooltip = this.label;
	}

	iconPath = {
		light: path.join(__filename, '..', '..', 'resources', 'light', 'folder.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'folder.svg')
	};

	contextValue = 'folder';
}

export class Blueprint extends vscode.TreeItem {

	constructor(
		public readonly label: string,
		public readonly description: string,
		public readonly collapsibleState: vscode.TreeItemCollapsibleState,
		public readonly command?: vscode.Command,
        

	) {
		super(label, collapsibleState);

		this.tooltip = this.label;
		this.description = this.description;
	}

	iconPath = {
		light: path.join(__filename, '..', '..', 'resources', 'light', 'dependency.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'dependency.svg')
	};

	contextValue = 'dependency';
}
