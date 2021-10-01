import * as vscode from 'vscode'
import { Profile } from './models';
import { ProfilesManager } from './profilesManager';
export class ProfilesProvider implements vscode.TreeDataProvider<Profile> {
    private _onDidChangeTreeData: vscode.EventEmitter<Profile | undefined | void> = new vscode.EventEmitter<Profile | undefined | void>();
	readonly onDidChangeTreeData: vscode.Event<Profile | undefined | void> = this._onDidChangeTreeData.event;
    constructor () {
        
    }

    refresh(): void {
		this._onDidChangeTreeData.fire();
	}

    refreshAllTrees(only_externals: boolean): void {
        //refresh the tree
        if (!only_externals)
		    this.refresh();
        //refresh the other explorers
        vscode.commands.executeCommand('blueprintsExplorerView.refreshEntry')
        vscode.commands.executeCommand('sandboxesExplorerView.refreshEntry')
    }

    async setAsDefault(profile: Profile): Promise<void> {
        //store the default profile value
        await ProfilesManager.getInstance().setActive(profile)
        //refresh
        this.refreshAllTrees(false);
	}

    removeEntry(profile: Profile): void {
        vscode.window.showInformationMessage(
            "Are you sure you want to remove this profile?",
            ...["No", "Yes"]
        )
        .then(async (answer) => {
            if (answer === "Yes") {
                await vscode.commands.executeCommand('remove_profile', profile.label)
		        this.refresh();
            }
        });
	}

    getTreeItem(element: Profile): vscode.TreeItem {
        return element;
	}

    getChildren(element?: Profile): Thenable<Profile[]> {
        return new Promise(async (resolve) => {
            if (element) {
                var result = []
                result.push(new vscode.TreeItem(`account: ${element.account}`, vscode.TreeItemCollapsibleState.None))
                result.push(new vscode.TreeItem(`space: ${element.space}`, vscode.TreeItemCollapsibleState.None))
                return resolve(result)
            }
            else {
                var profilesMngr = ProfilesManager.getInstance()
                var profiles = []
                await vscode.commands.executeCommand('list_torque_profiles')
                .then(async (result:Array<string>) => 
                {                  
                    var default_profile = (profilesMngr.getActive() === undefined) ? "" : profilesMngr.getActive().label
                    var description = ""
                    var default_found = false;

                    for (var profile of result) {
                        var account = (profile['account'] === "") ? 'undefined' : profile['account']
                        if (profile['profile'] == default_profile) {
                            description = "[default]";
                            default_found = true;
                        }
                        else
                            description = "";

                        profiles.push(new Profile(
                            profile['profile'],description,
                            vscode.TreeItemCollapsibleState.Collapsed,
                            account,
                            profile['space']))
                    }
                    if (default_found === false) {
                        if (profiles.length > 0) {
                            await profilesMngr.setActive(profiles[0])
                            profiles[0].description = "[default]";
                        }
                        else
                            await profilesMngr.setActive(undefined)
                        this.refreshAllTrees(true);
                    }
                    resolve(profiles)
                })
            }
        });
    }
}
