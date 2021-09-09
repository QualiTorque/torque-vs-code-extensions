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

		console.log(element);
		return Promise.resolve(this.getOnlineBlueprints());
		
	}

	/**
	 * Given the path to package.json, read all its dependencies and devDependencies.
	 */
	private getOnlineBlueprints(): Blueprint[] {
		if (this.connections) {
			const templist = '[{"blueprint_name":"dff","description":null,"url":"https://github.com/kalsky/samples/blob/master/blueprints/dff.yaml","inputs":[],"enabled":false,"last_modified":"2021-07-13T15:22:09","modified_by":"Yaniv Kalsky","applications":[],"services":[],"clouds":[],"is_sample":false,"artifacts":{},"errors":[{"message":"Bad blueprint YAML file","name":"Blueprint YAML error","code":"BAD_BLUEPRINT_YAML_ERROR"}],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/dff","method":"DELETE"}]},{"blueprint_name":"empty-bp-empty-app","description":"empty vm","url":"https://github.com/kalsky/samples/blob/master/blueprints/empty-bp-empty-app.yaml","inputs":[{"name":"VM_SIZE","default_value":"Standard_B1s","display_style":"normal","description":null,"optional":false},{"name":"INPUT2","default_value":null,"display_style":"normal","description":null,"optional":false},{"name":"INPUT3","default_value":"0","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-09-09T16:18:48","modified_by":"Yaniv Kalsky","applications":[{"name":"empty-app","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"azure","cloud_account_name":"Azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"uswest2","name":null}}],"is_sample":false,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/empty-bp-empty-app","method":"DELETE"}]},{"blueprint_name":"Java Spring","description":"A Java Spring website deployed on a TomCat server and MySQL database\\n","url":"https://github.com/kalsky/samples/blob/master/blueprints/Java Spring.yaml","inputs":[{"name":"DB_USER","default_value":"root","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"12345","display_style":"masked","description":"please set the root database passwor","optional":false},{"name":"DB_NAME","default_value":"demo_db","display_style":"normal","description":null,"optional":false}],"enabled":false,"last_modified":"2021-07-13T15:22:09","modified_by":"Yaniv Kalsky","applications":[{"name":"mysql","version":"","icon_url":null},{"name":"java-spring-website","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"aws","cloud_account_name":"aws","compute_service":{"name":"aws/EC2","type":"EC2","created_date":"2021-01-19T18:17:01.879231","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"eu-west-1","name":"EU (Ireland)"}}],"is_sample":false,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/Java%20Spring","method":"DELETE"}]},{"blueprint_name":"New Web App","description":"An angular website deployment\\n","url":"https://github.com/kalsky/samples/blob/master/blueprints/New Web App.yaml","inputs":[{"name":"DB_USER","default_value":"postgress","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"pgrs1234!","display_style":"masked","description":"please set the root database passwor","optional":false},{"name":"DB_NAME","default_value":"halpdesk","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-04-01T19:17:47","modified_by":"Yaniv Kalsky","applications":[{"name":"psql","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"aws","cloud_account_name":"aws","compute_service":{"name":"aws/EC2","type":"EC2","created_date":"2021-01-19T18:17:01.879231","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"eu-west-1","name":"EU (Ireland)"}}],"is_sample":false,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/New%20Web%20App","method":"DELETE"}]},{"blueprint_name":"django-dashboard-black","description":"django dashboard black\\n","url":"https://github.com/kalsky/samples/blob/master/blueprints/django-dashboard-black.yaml","inputs":[{"name":"INSTANCE_SIZE","default_value":"Standard_D2a_v4","display_style":"normal","description":null,"optional":false}],"enabled":false,"last_modified":"2021-08-04T14:28:27","modified_by":"Yaniv Kalsky","applications":[{"name":"ddb-app","version":"","icon_url":null},{"name":"empty-app","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"azure","cloud_account_name":"Azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"westus2","name":null}}],"is_sample":false,"artifacts":{},"errors":[{"message":"Your blueprint is missing a dependency between ddb-app and empty-app. Using \'colony.applications.empty-app.outputs.OUTPUT1\' requires the ddb-app to explicitly include a dependency using a \'depends on\' attribute","name":"Blueprint output is not valid","code":"BLUEPRINT_OUTPUT_VARIABLE_MUST_BE_DEPENDS"}],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/django-dashboard-black","method":"DELETE"}]},{"blueprint_name":"Web App","description":"An angular website deployment\\n","url":"https://github.com/kalsky/samples/blob/master/blueprints/Web App.yaml","inputs":[{"name":"DB_USER","default_value":"postgress","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"pgrs1234!","display_style":"masked","description":"please set the root database passwor","optional":false},{"name":"DB_NAME","default_value":"halpdesk","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-09-09T16:19:09","modified_by":"Yaniv Kalsky","applications":[{"name":"psql","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"azure","cloud_account_name":"azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"uswest2","name":null}}],"is_sample":false,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/Web%20App","method":"DELETE"}]}]';
			const blueprintsJson = JSON.parse(templist);

			const toBp = (blueprintName: string, description: string, space: string, inputs: Array<string>): Blueprint => {
				return new Blueprint(blueprintName, description, vscode.TreeItemCollapsibleState.None, {
					command: 'extension.openReserveForm',
					title: '',
					arguments: [blueprintName, space, inputs]
				});
			};
			const conn = this.connections[0];
			const bps = [];
			for (var b=0; b<blueprintsJson.length; b++)
			{
                console.log(blueprintsJson[b]);
				const bpj = blueprintsJson[b];
				if (bpj.errors.length==0)
				{ 
					var bp = toBp(bpj.blueprint_name, bpj.description, conn["space"], bpj.inputs);
					bps.push(bp);
				}
			}

			return bps;
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
		public readonly description: string,
		//private readonly version: string,
		public readonly collapsibleState: vscode.TreeItemCollapsibleState,
		public readonly command?: vscode.Command,
        

	) {
		super(label, collapsibleState);

		this.tooltip = this.label;
		this.description = this.description;
	}

	iconPath = {
		light: path.join(__filename, '..', '..', 'resources', 'light', 'dependency.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'dependency.svg')
	};

	contextValue = 'dependency';
}
