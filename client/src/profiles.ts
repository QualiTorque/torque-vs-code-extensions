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
        return element;
	}

    getChildren(element?: Profile): Thenable<Profile[]> {
        return new Promise(async (resolve) => {
            if (element) {
                return []
            }
            else {
                var profiles = []
                vscode.commands.executeCommand('list_torque_profiles')
                .then((result:Array<string>) => 
                {
                    for (var profile of result) {  
                        profiles.push(new Profile(profile['profile'], vscode.TreeItemCollapsibleState.None))
                    }
                    resolve(profiles)

                })
            }
        });
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
		light: path.join(__filename, '..', '..', 'resources', 'light', 'profile.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'profile.svg')
	};

	contextValue = 'dependency';

}