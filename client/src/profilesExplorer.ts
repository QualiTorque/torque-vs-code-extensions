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
                const result = []
                result.push(new vscode.TreeItem(`account: ${element.account}`, vscode.TreeItemCollapsibleState.None))
                result.push(new vscode.TreeItem(`space: ${element.space}`, vscode.TreeItemCollapsibleState.None))
                return resolve(result)
            }
            else {
                const profilesMngr = ProfilesManager.getInstance()
                const profiles = []
                await vscode.commands.executeCommand('list_torque_profiles')
                .then(async (result:Array<string>) => 
                {
                    const activeProfile = profilesMngr.getActive();
                    const activeProfileName = (activeProfile === undefined) ? "" : activeProfile.label;
                    const activeSpaceName = (activeProfile === undefined) ? "" : activeProfile.space;

                    let description = ""
                    let defaultFound = false;

                    for (let profile of result) {
                        const account = (profile['account'] === "") ? 'undefined' : profile['account']

                        if (profile['profile'] == activeProfileName) {
                            description = "[active]";
                            defaultFound = true;
                        }
                        else
                            description = "";

                        const profileTreeItem = new Profile(
                            profile['profile'],
                            description,
                            vscode.TreeItemCollapsibleState.Collapsed,
                            account,
                            profile['space'])

                        profiles.push(profileTreeItem)

                        if (description != "" && activeSpaceName != profile['space']) {
                            await profilesMngr.setActive(profileTreeItem)
                            this.refreshAllTrees(true);
                        }
                    }

                    if (defaultFound === false) {
                        if (profiles.length > 0) {
                            await profilesMngr.setActive(profiles[0])
                            profiles[0].description = "[active]";
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
