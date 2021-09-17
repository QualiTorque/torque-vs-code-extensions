import { read } from 'fs';
import * as vscode from 'vscode'
import * as path from 'path';

export class ProfilesProvider implements vscode.TreeDataProvider<Profile> {
    private _onDidChangeTreeData: vscode.EventEmitter<Profile | undefined | void> = new vscode.EventEmitter<Profile | undefined | void>();
	readonly onDidChangeTreeData: vscode.Event<Profile | undefined | void> = this._onDidChangeTreeData.event;
    constructor () {
        console.log("start")
    }

    getTreeItem(element: Profile): vscode.TreeItem {
        console.log('item');
		return element;
	}

    getChildren(element?: Profile): Thenable<Profile[]> {
        var profiles = []
 

        console.log('children');
        vscode.commands.executeCommand('list_torque_profiles')

            .then((result) =>
            {
                console.log(result)
                for (var profile of result) {  // (TODO): not sure how to use typecasting here
                    profiles.push(new Profile(profile['profile'], vscode.TreeItemCollapsibleState.Collapsed))
                }
                // return Promise.resolve(result)
                return Promise.resolve(profiles)

            });
        return Promise.resolve(profiles)
    }
}

export class Profile extends vscode.TreeItem {
    constructor(
        public readonly label : string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,

    ) {
        super(label,collapsibleState)
        this.tooltip = this.label
    }
    iconPath = {
		light: path.join(__filename, '..', '..', 'resources', 'light', 'dependency.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'dependency.svg')
	};

	contextValue = 'dependency';

}