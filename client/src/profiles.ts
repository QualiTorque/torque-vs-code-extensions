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

    async setAsDefault(profile: Profile): Promise<void> {
        console.log(profile.label);
        //store the default profile value
        await vscode.workspace.getConfiguration("torque").update("default_profile", profile.label, vscode.ConfigurationTarget.Workspace);
        //refresh
        this.refreshAllTrees();
	}

    removeEntry(profile: Profile): void {
        console.log("Removing " + profile.label);

        vscode.commands.executeCommand('remove_profile', profile.label)
		this.refresh();
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
                var profiles = []
                await vscode.commands.executeCommand('list_torque_profiles')
                .then(async (result:Array<string>) => 
                {
                    var default_profile = vscode.workspace.getConfiguration("torque").get<string>("default_profile", "");
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
                            await vscode.workspace.getConfiguration("torque").update(
                                "default_profile",
                                profiles[0].label,
                                vscode.ConfigurationTarget.Workspace);
                            profiles[0].description = "[default]";
                        }
                        else 
                            await vscode.workspace.getConfiguration("torque").update(
                                "default_profile", "", vscode.ConfigurationTarget.Workspace);
                        // TODO: Condider having a method to refresh only external explorers
                        await vscode.commands.executeCommand('blueprintsExplorerView.refreshEntry')
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
        public account : string,
        public space: string

    ) {
        super(label,collapsibleState)
        this.tooltip = `account: ${this.account}\nspace: ${this.space}`      
    }
    
    iconPath = new vscode.ThemeIcon("account");

	contextValue = 'space';

}