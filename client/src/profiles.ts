import { read } from 'fs';
import * as vscode from 'vscode'
import * as path from 'path';

export class ProfilesProvider implements vscode.TreeDataProvider<Profile> {
    private _onDidChangeTreeData: vscode.EventEmitter<Profile | undefined | void> = new vscode.EventEmitter<Profile | undefined | void>();
	readonly onDidChangeTreeData: vscode.Event<Profile | undefined | void> = this._onDidChangeTreeData.event;
    constructor () {
        console.log("start")
    }

    refresh(): void {
		this._onDidChangeTreeData.fire();
	}

    refreshAllTrees(): void {
        //refresh the tree
		this.refresh();
        //refresh the other explorers
        vscode.commands.executeCommand('blueprintsExplorerView.refreshEntry')
    }

    setAsDefault(profile: Profile): void {
        console.log(profile.label);
        //store the default profile value

        //refresh
        this.refreshAllTrees();
	}

    removeEntry(profile: Profile): void {
        console.log("Removing " + profile.label);

        vscode.commands.executeCommand('remove_profile', profile.label)
        //refresh the tree
		this.refreshAllTrees();
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
                    var default_profile = vscode.workspace.getConfiguration("torque").get<string>("default_profile", "");
                    for (var profile of result) {  
                        if (profile['profile'] == default_profile)
                            profiles.push(new Profile(profile['profile'], '(default)', vscode.TreeItemCollapsibleState.None))
                        else
                            profiles.push(new Profile(profile['profile'], '', vscode.TreeItemCollapsibleState.None))
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
        public description : string,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,

    ) {
        super(label,collapsibleState)
        this.tooltip = this.label        
    }
    
    iconPath = new vscode.ThemeIcon("account");

	contextValue = 'space';

}