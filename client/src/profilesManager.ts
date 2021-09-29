import { Profile } from "./models";
import * as vscode from 'vscode';


// singleton
export class ProfilesManager {
    private static instance: ProfilesManager | undefined;
    private readonly profiles: Profile[] = [];
    private activeProfile: Profile | undefined;

    private constructor() {}

    public async setActive(profile: Profile) {
        if (this.profiles.includes(profile)) {
            this.activeProfile = profile;
            await vscode.workspace.getConfiguration("torque").update("default_profile", profile.label, vscode.ConfigurationTarget.Workspace);
        }
    }

    public getActive(){
        if (this.activeProfile === undefined) 
            if (this.profiles.length > 0)
                this.setActive(this.profiles[0]);
            else
                return undefined;

        return this.activeProfile;
    }

    public addProfile(profile: Profile) {
        this.profiles.push(profile);
    }

    public async removeProfile(profile: Profile) {
        const index = this.profiles.indexOf(profile);
        if (index > -1)
            this.profiles.splice(index, 1)

        if (JSON.stringify(profile) === JSON.stringify(this.activeProfile))
            if (this.profiles.length > 0)
                this.setActive(this.profiles[0])
            else {
                await vscode.workspace.getConfiguration("torque").update("default_profile", "", vscode.ConfigurationTarget.Workspace);
                this.activeProfile = undefined;
            }

    }

    public static getInstance(): ProfilesManager {
        if (!ProfilesManager.instance) {
            ProfilesManager.instance = new ProfilesManager()
        }

        return ProfilesManager.instance
    }

}