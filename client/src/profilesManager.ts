import { Profile } from "./models";
import * as vscode from 'vscode';


// singleton
export class ProfilesManager {
    private static instance: ProfilesManager | undefined;
    private activeProfile: Profile | undefined;

    private constructor() {}

    public async setActive(profile: Profile | undefined) {
        this.activeProfile = profile;
        await this._updateConfiguration(profile);
    }

    public getActive(){
        if (this.activeProfile === undefined) {
            // try to load from file
            this.activeProfile = this._loadConfiguration();
        }
        return this.activeProfile;
    }

    public static getInstance(): ProfilesManager {
        if (!ProfilesManager.instance) {
            ProfilesManager.instance = new ProfilesManager()
        }

        return ProfilesManager.instance
    }

    private async _updateConfiguration(profile: Profile) : Promise<void> {
        if (profile !== undefined) 
            await vscode.workspace.getConfiguration("torque").update("activeProfile", profile.label, vscode.ConfigurationTarget.Workspace);
        else
            await vscode.workspace.getConfiguration("torque").update("activeProfile", "", vscode.ConfigurationTarget.Workspace);        
    }

    private _loadConfiguration() : Profile {
        const profile = vscode.workspace.getConfiguration('torque').get<string>("activeProfile", "");
        
        return new Profile(profile, '', vscode.TreeItemCollapsibleState.None, "", "");
    }

}