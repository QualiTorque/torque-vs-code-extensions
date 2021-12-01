import * as vscode from 'vscode'
import { Blueprint } from './models'
import { ProfilesManager } from './profilesManager'

export class BlueprintsProvider implements vscode.TreeDataProvider<Blueprint> {
    private _onDidChangeTreeData: vscode.EventEmitter<Blueprint | undefined | void> = new vscode.EventEmitter<Blueprint | undefined | void>()
    readonly onDidChangeTreeData: vscode.Event<Blueprint | undefined | void> = this._onDidChangeTreeData.event
    private firstLoad = true
    
    refresh(): void {
        this._onDidChangeTreeData.fire()
    }

    getTreeItem(element: Blueprint): vscode.TreeItem {
        return element
    }

    getChildren(element?: Blueprint): Thenable<Blueprint[]> {
        return new Promise(async (resolve) => {
            if (!element && this.firstLoad) {
                this.firstLoad = false
                return resolve([])
            }

            if (element) {
                return resolve([])
            } else {
                const activeProfile = (ProfilesManager.getInstance().getActive() === undefined) ? '' : ProfilesManager.getInstance().getActive().label
                const results = []

                if (activeProfile === '') {
                    vscode.window.showInformationMessage('No default profile is defined');
                    results.push(this.getLoginTreeItem())
                    return resolve(results)
                }
                else {
                    var bps = []

                    vscode.commands.executeCommand('list_blueprints')
                    .then(async (result:string) => {
                        if (result.length > 0) {
                            const blueprintsJson = JSON.parse(result)

                            const toBp = (blueprintName: string, description: string, isSample: boolean, inputs: Array<string>, artifacts: string, branch: string):
                            Blueprint => {
                                let cleanName = blueprintName
                                if (isSample) {
                                    cleanName = cleanName.replace('[Sample]', '')
                                }
                                return new Blueprint(cleanName, description, vscode.TreeItemCollapsibleState.None, {
                                    command: 'extension.openReserveForm',
                                    title: '',
                                    arguments: [blueprintName, inputs, artifacts, branch]
                                })
                            };

                            for (let b = 0; b < blueprintsJson.length; b++) {
                                const bpj = blueprintsJson[b]
                                if (bpj.errors.length === 0 && bpj.enabled) {
                                    const re = new RegExp('(?<=blob\/)(.*)(?=\/blueprints)')
                                    var branch
                                    if (bpj.url) {
                                        branch = bpj.url.match(re)[0];
                                        const bp = toBp(bpj.blueprint_name, bpj.description, bpj.is_sample, bpj.inputs, bpj.artifacts, branch)
                                        bps.push(bp)
                                    }
                                }
                            }
                            return resolve(bps)
                        }
                        else return resolve([])
                    })
                }
            }
        })
    }

    private getLoginTreeItem() : vscode.TreeItem {
        const message = new vscode.TreeItem('Login to Torque', vscode.TreeItemCollapsibleState.None)
        message.command = { command: 'profilesView.addProfile', title: 'Login' }
        message.tooltip = "Currently you don't have any profiles configured. Login to Torque in order to create the first profile"
        return message
    }
}
