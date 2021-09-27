import * as vscode from 'vscode';
import * as path from 'path';

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
	private getOnlineBlueprints(profile): Sandbox[] {
        const sbs =  
		const blueprintsJson = JSON.parse(templist);

		// const toBp = (blueprintName: string, description: string, is_sample: boolean, space: string, inputs: Array<string>, artifacts: string):
		const toBp = (blueprintName: string, description: string, is_sample: boolean, inputs: Array<string>, artifacts: string):
		     => {
			var cleanName = blueprintName;
			if (is_sample)
				cleanName = cleanName.replace('[Sample]', '')
			return new Blueprint(cleanName, description, vscode.TreeItemCollapsibleState.None, {
				command: 'extension.openReserveForm',
				title: '',
				arguments: [blueprintName, inputs, artifacts]
				// arguments: [blueprintName, space, inputs, artifacts]
			});
		};

		const bps = [];
		for (var b=0; b<blueprintsJson.length; b++)
		{
			const bpj = blueprintsJson[b];
			if (bpj.errors.length==0 && bpj.enabled)
			{ 
				var bp = toBp(bpj.blueprint_name, bpj.description, bpj.is_sample, bpj.inputs, bpj.artifacts);
				// var bp = toBp(bpj.blueprint_name, bpj.description, bpj.is_sample, conn["space"], bpj.inputs, bpj.artifacts);
				bps.push(bp);
			}
		}

		return bps;
	}

}

export class Sandbox extends vscode.TreeItem {

	constructor(
		public readonly label: string,
		public readonly description: string,
		//private readonly version: string,
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
