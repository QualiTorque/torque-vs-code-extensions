import * as vscode from 'vscode';
import * as fs from 'fs';
import * as path from 'path';

export class BlueprintsProvider implements vscode.TreeDataProvider<Blueprint> {

	private _onDidChangeTreeData: vscode.EventEmitter<Blueprint | undefined | void> = new vscode.EventEmitter<Blueprint | undefined | void>();
	readonly onDidChangeTreeData: vscode.Event<Blueprint | undefined | void> = this._onDidChangeTreeData.event;
    connections: Array<object>;

	constructor() {
        console.log("before get connections");
        this.connections = vscode.workspace.getConfiguration("torque").get<Array<object>>("connections", []);
        if (this.connections)
        { 
            for (var c=0; c<this.connections.length; c++)
                console.log(this.connections[c]);
        }
        else
            console.log("can't get connections");
	}

	refresh(): void {
		this._onDidChangeTreeData.fire();
	}

	getTreeItem(element: Blueprint): vscode.TreeItem {
		return element;
	}

	getChildren(element?: Blueprint): Thenable<Blueprint[]> {
		if (!this.connections) {
			vscode.window.showInformationMessage('No connections defined in the settings');
			return Promise.resolve([]);
		}

		// if (element) {
		// 	return Promise.resolve(this.getDepsInPackageJson(path.join(this.workspaceRoot, 'node_modules', element.label, 'package.json')));
		// } else {
		// 	const packageJsonPath = path.join(this.workspaceRoot, 'package.json');
		// 	if (this.pathExists(packageJsonPath)) {
		// 		return Promise.resolve(this.getDepsInPackageJson(packageJsonPath));
		// 	} else {
		// 		vscode.window.showInformationMessage('Workspace has no package.json');
		// 		return Promise.resolve([]);
		// 	}
		// }

	}

	/**
	 * Given the path to package.json, read all its dependencies and devDependencies.
	 */
	private getDepsInPackageJson(packageJsonPath: string): Blueprint[] {
		if (this.pathExists(packageJsonPath)) {
			const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));

			const toDep = (moduleName: string, version: string): Blueprint => {
				// if (this.pathExists(path.join(this.workspaceRoot, 'node_modules', moduleName))) {
				// 	return new Dependency(moduleName, version, vscode.TreeItemCollapsibleState.Collapsed);
				// } else {
				// 	return new Dependency(moduleName, version, vscode.TreeItemCollapsibleState.None, {
				// 		command: 'extension.openPackageOnNpm',
				// 		title: '',
				// 		arguments: [moduleName]
				// 	});
				// }
                return null;
			};

			const deps = packageJson.dependencies
				? Object.keys(packageJson.dependencies).map(dep => toDep(dep, packageJson.dependencies[dep]))
				: [];
			const devDeps = packageJson.devDependencies
				? Object.keys(packageJson.devDependencies).map(dep => toDep(dep, packageJson.devDependencies[dep]))
				: [];
			return deps.concat(devDeps);
		} else {
			return [];
		}
	}

	private pathExists(p: string): boolean {
		try {
			fs.accessSync(p);
		} catch (err) {
			return false;
		}

		return true;
	}
}

export class Blueprint extends vscode.TreeItem {

	constructor(
		public readonly label: string,
		private readonly version: string,
		public readonly collapsibleState: vscode.TreeItemCollapsibleState,
		public readonly command?: vscode.Command,
        public readonly description?: string

	) {
		super(label, collapsibleState);

		this.tooltip = `${this.label}-${this.version}`;
		this.description = this.description;
	}

	iconPath = {
		light: path.join(__filename, '..', '..', 'resources', 'light', 'dependency.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'dependency.svg')
	};

	contextValue = 'dependency';
}
