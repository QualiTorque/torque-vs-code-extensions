import * as vscode from 'vscode';
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
		return new Promise(async (resolve) => {
			const default_profile = vscode.workspace.getConfiguration('torque').get<string>("default_profile", "");
			var results = []

			if (element) {
				console.log("element")
				return resolve(results);
			} else {
				if (default_profile === "") {
					vscode.window.showInformationMessage('No default profile is defined');
					results.push(this.getLoginTreeItem())
					return resolve(results);
				}
				else
					return resolve(this.getOnlineBlueprints(default_profile))
			}
		});
	}

	private getLoginTreeItem() : vscode.TreeItem {
		var message = new vscode.TreeItem("Login to Torque", vscode.TreeItemCollapsibleState.None)
		message.command = {command: 'profilesView.addProfile', 'title': 'Login'}
		message.tooltip = "Currently you don't have any profiles confifured. Login to Torque in order to create the first profile"
		return message
	}

	/**
	 * Given the path to package.json, read all its dependencies and devDependencies.
	 */
	private async getOnlineBlueprints(profile: string): Promise<Blueprint[]> {
		// TODO: use profile when run torque cli command
		// if (profile == 'test')
		// 	var templist = '[{"blueprint_name":"dff","description":null,"url":"https://github.com/kalsky/samples/blob/master/blueprints/dff.yaml","inputs":[],"enabled":true,"last_modified":"2021-07-13T15:22:09","modified_by":"Yaniv Kalsky","applications":[],"services":[],"clouds":[],"is_sample":false,"artifacts":{"empty-app":"aaa.tz","ddb-app":""},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/dff","method":"DELETE"}]},{"blueprint_name":"empty-bp-empty-app","description":"empty vm","url":"https://github.com/kalsky/samples/blob/master/blueprints/empty-bp-empty-app.yaml","inputs":[{"name":"VM_SIZE","default_value":"Standard_B1s","display_style":"normal","description":null,"optional":false},{"name":"INPUT2","default_value":null,"display_style":"normal","description":null,"optional":false},{"name":"INPUT3","default_value":"0","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-09-09T16:18:48","modified_by":"Yaniv Kalsky","applications":[{"name":"empty-app","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"azure","cloud_account_name":"Azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"uswest2","name":null}}],"is_sample":false,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/empty-bp-empty-app","method":"DELETE"}]},{"blueprint_name":"Java Spring","description":"A Java Spring website deployed on a TomCat server and MySQL database\\n","url":"https://github.com/kalsky/samples/blob/master/blueprints/Java Spring.yaml","inputs":[{"name":"DB_USER","default_value":"root","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"12345","display_style":"masked","description":"please set the root database passwor","optional":false},{"name":"DB_NAME","default_value":"demo_db","display_style":"normal","description":null,"optional":false}],"enabled":false,"last_modified":"2021-07-13T15:22:09","modified_by":"Yaniv Kalsky","applications":[{"name":"mysql","version":"","icon_url":null},{"name":"java-spring-website","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"aws","cloud_account_name":"aws","compute_service":{"name":"aws/EC2","type":"EC2","created_date":"2021-01-19T18:17:01.879231","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"eu-west-1","name":"EU (Ireland)"}}],"is_sample":false,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/Java%20Spring","method":"DELETE"}]},{"blueprint_name":"New Web App","description":"An angular website deployment\\n","url":"https://github.com/kalsky/samples/blob/master/blueprints/New Web App.yaml","inputs":[{"name":"DB_USER","default_value":"postgress","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"pgrs1234!","display_style":"masked","description":"please set the root database passwor","optional":false},{"name":"DB_NAME","default_value":"halpdesk","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-04-01T19:17:47","modified_by":"Yaniv Kalsky","applications":[{"name":"psql","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"aws","cloud_account_name":"aws","compute_service":{"name":"aws/EC2","type":"EC2","created_date":"2021-01-19T18:17:01.879231","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"eu-west-1","name":"EU (Ireland)"}}],"is_sample":false,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/New%20Web%20App","method":"DELETE"}]},{"blueprint_name":"django-dashboard-black","description":"django dashboard black\\n","url":"https://github.com/kalsky/samples/blob/master/blueprints/django-dashboard-black.yaml","inputs":[{"name":"INSTANCE_SIZE","default_value":"Standard_D2a_v4","display_style":"normal","description":null,"optional":false}],"enabled":false,"last_modified":"2021-08-04T14:28:27","modified_by":"Yaniv Kalsky","applications":[{"name":"ddb-app","version":"","icon_url":null},{"name":"empty-app","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"azure","cloud_account_name":"Azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"westus2","name":null}}],"is_sample":false,"artifacts":{},"errors":[{"message":"Your blueprint is missing a dependency between ddb-app and empty-app. Using \'colony.applications.empty-app.outputs.OUTPUT1\' requires the ddb-app to explicitly include a dependency using a \'depends on\' attribute","name":"Blueprint output is not valid","code":"BLUEPRINT_OUTPUT_VARIABLE_MUST_BE_DEPENDS"}],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/django-dashboard-black","method":"DELETE"}]},{"blueprint_name":"Web App","description":"An angular website deployment\\n","url":"https://github.com/kalsky/samples/blob/master/blueprints/Web App.yaml","inputs":[{"name":"DB_USER","default_value":"postgress","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"pgrs1234!","display_style":"masked","description":"please set the root database passwor","optional":false},{"name":"DB_NAME","default_value":"halpdesk","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-09-09T16:19:09","modified_by":"Yaniv Kalsky","applications":[{"name":"psql","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"azure","cloud_account_name":"azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"uswest2","name":null}}],"is_sample":false,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Trial/catalog/Web%20App","method":"DELETE"}]}]';
		// else
		// 	var templist = '[{"blueprint_name":"[Sample]WordPress Basic Stack (AWS)","description":"LAMP WordPress stack (Linux, Apache, MySQL, PHP)","url":"https://github.com/cloudshell-colony/samples/blob/master/blueprints/WordPress Basic Stack (AWS).yaml","inputs":[{"name":"DB_USER","default_value":"root","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"12345","display_style":"masked","description":"please set the root database password","optional":false},{"name":"DB_NAME","default_value":"wordpress_demo","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-01-11T10:53:06","modified_by":"Colony","applications":[{"name":"mysql","version":"","icon_url":null},{"name":"wordpress","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"","cloud_account_name":"AWS","compute_service":{"name":null,"type":null,"created_date":"0001-01-01T00:00:00","created_by":"N/A","user_defined":false},"region":{"id":"eu-west-1","name":null}}],"is_sample":true,"artifacts":{},"errors":[{"message":"This sample will be available for you after adding a valid cloud account","name":"Sample blueprint unknown cloud account","code":"SAMPLE_UNKNOWN_CLOUD_ACCOUNT"}],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog/%5BSample%5DWordPress%20Basic%20Stack%20(AWS)","method":"DELETE"}]},{"blueprint_name":"[Sample]Integration Environment (VM & Azure Database)","description":"Java application with a managed Azure database deployed with TerraForm.\\n","url":"https://github.com/cloudshell-colony/samples/blob/master/blueprints/Integration Environment (VM & Azure Database).yaml","inputs":[{"name":"DB_USER","default_value":"colony","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"sv4YPTPs7fN&","display_style":"masked","description":"Database server password must contain from 8 to 128 characters. Your password must contain characters from three of the following categories: English uppercase letters, English lowercase letters, numbers (0-9), and non-alphanumeric characters (!, $, #, %, and so on)\\n","optional":false},{"name":"DB_NAME","default_value":"demo_db","display_style":"normal","description":null,"optional":false},{"name":"MANAGED_IDENTITY","default_value":null,"display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-01-11T10:53:06","modified_by":"Colony","applications":[{"name":"java-spring-website","version":"","icon_url":null}],"services":[{"name":"azure-mysql","type":"TerraForm"}],"clouds":[{"provider":"azure","cloud_account_name":"azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"westeurope","name":null}}],"is_sample":true,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog/%5BSample%5DIntegration%20Environment%20(VM%20%26%20Azure%20Database)","method":"DELETE"}]},{"blueprint_name":"[Sample]Dev & Test Environment (All-in-One, AWS)","description":"A simple multi-tier application deployed on a single EC2 instance.\\n","url":"https://github.com/cloudshell-colony/samples/blob/master/blueprints/Dev & Test Environment (All-in-One, AWS).yaml","inputs":[{"name":"DB_USER","default_value":"root","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"12345","display_style":"masked","description":"please set the root database password","optional":false},{"name":"DB_NAME","default_value":"demo_db","display_style":"normal","description":null,"optional":false}],"enabled":false,"last_modified":"2021-06-03T14:31:48","modified_by":"Colony","applications":[{"name":"mysql","version":"","icon_url":null},{"name":"java-spring-website","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"","cloud_account_name":"AWS","compute_service":{"name":null,"type":null,"created_date":"0001-01-01T00:00:00","created_by":"N/A","user_defined":false},"region":{"id":"eu-west-1","name":null}}],"is_sample":true,"artifacts":{},"errors":[{"message":"This sample will be available for you after adding a valid cloud account","name":"Sample blueprint unknown cloud account","code":"SAMPLE_UNKNOWN_CLOUD_ACCOUNT"}],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog/%5BSample%5DDev%20%26%20Test%20Environment%20(All-in-One,%20AWS)","method":"DELETE"}]},{"blueprint_name":"[Sample]Staging Environment (Amazon Aurora Cluster)","description":"A complex cloud architecture of a web application and a managed database cluster deployed with TerraForm.\\n","url":"https://github.com/cloudshell-colony/samples/blob/master/blueprints/Staging Environment (Amazon Aurora Cluster).yaml","inputs":[{"name":"DB_USER","default_value":"root","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"Colony!123","display_style":"masked","description":"please set the root database password","optional":false},{"name":"DB_NAME","default_value":"demo_db","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2021-01-11T10:53:06","modified_by":"Colony","applications":[{"name":"java-spring-website","version":"","icon_url":null}],"services":[{"name":"rds-mysql-aurora-cluster","type":"TerraForm"}],"clouds":[{"provider":"","cloud_account_name":"AWS","compute_service":{"name":null,"type":null,"created_date":"0001-01-01T00:00:00","created_by":"N/A","user_defined":false},"region":{"id":"eu-west-1","name":null}}],"is_sample":true,"artifacts":{},"errors":[{"message":"This sample will be available for you after adding a valid cloud account","name":"Sample blueprint unknown cloud account","code":"SAMPLE_UNKNOWN_CLOUD_ACCOUNT"}],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog/%5BSample%5DStaging%20Environment%20(Amazon%20Aurora%20Cluster)","method":"DELETE"}]},{"blueprint_name":"[Sample]WordPress Basic Stack (Azure)","description":"LAMP WordPress stack (Linux, Apache, MySQL, PHP)","url":"https://github.com/cloudshell-colony/samples/blob/master/blueprints/WordPress Basic Stack (Azure).yaml","inputs":[{"name":"DB_USER","default_value":"root","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"12345","display_style":"masked","description":"please set the root database password","optional":false},{"name":"DB_NAME","default_value":"wordpress_demo","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2020-11-24T18:27:02","modified_by":"Colony","applications":[{"name":"mysql","version":"","icon_url":null},{"name":"wordpress","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"azure","cloud_account_name":"azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"westeurope","name":null}}],"is_sample":true,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog/%5BSample%5DWordPress%20Basic%20Stack%20(Azure)","method":"DELETE"}]},{"blueprint_name":"[Sample]Integration Environment (EC2 & AWS RDS)","description":"Java application with a managed RDS database deployed with TerraForm.\\n","url":"https://github.com/cloudshell-colony/samples/blob/master/blueprints/Integration Environment (EC2 & AWS RDS).yaml","inputs":[{"name":"DB_USER","default_value":"root","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"Colony!123","display_style":"masked","description":"please set the root database password","optional":false},{"name":"DB_NAME","default_value":"demo_db","display_style":"normal","description":null,"optional":false}],"enabled":false,"last_modified":"2021-01-11T10:53:06","modified_by":"Colony","applications":[{"name":"java-spring-website","version":"","icon_url":null}],"services":[{"name":"rds-mysql","type":"TerraForm"}],"clouds":[{"provider":"","cloud_account_name":"AWS","compute_service":{"name":null,"type":null,"created_date":"0001-01-01T00:00:00","created_by":"N/A","user_defined":false},"region":{"id":"eu-west-1","name":null}}],"is_sample":true,"artifacts":{},"errors":[{"message":"This sample will be available for you after adding a valid cloud account","name":"Sample blueprint unknown cloud account","code":"SAMPLE_UNKNOWN_CLOUD_ACCOUNT"}],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog/%5BSample%5DIntegration%20Environment%20(EC2%20%26%20AWS%20RDS)","method":"DELETE"}]},{"blueprint_name":"[Sample]Dev & Test Environment (All-in-One, Azure)","description":"A simple multi-tier application deployed on a single Azure VM.\\n","url":"https://github.com/cloudshell-colony/samples/blob/master/blueprints/Dev & Test Environment (All-in-One, Azure).yaml","inputs":[{"name":"DB_USER","default_value":"root","display_style":"normal","description":null,"optional":false},{"name":"DB_PASS","default_value":"12345","display_style":"masked","description":"please set the root database password","optional":false},{"name":"DB_NAME","default_value":"demo_db","display_style":"normal","description":null,"optional":false}],"enabled":true,"last_modified":"2020-11-24T18:27:02","modified_by":"Colony","applications":[{"name":"mysql","version":"","icon_url":null},{"name":"java-spring-website","version":"","icon_url":null}],"services":[],"clouds":[{"provider":"azure","cloud_account_name":"azure","compute_service":{"name":"azure/AZURE_VM","type":"AZURE_VM","created_date":"2021-01-19T18:52:53.172172","created_by":"Yaniv Kalsky","user_defined":false},"region":{"id":"westeurope","name":null}}],"is_sample":true,"artifacts":{},"errors":[],"links":[{"rel":"add blueprint to catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog","method":"POST"},{"rel":"remove blueprint from catalog","href":"https://trial-30879ec6.cloudshellcolony.com/api/spaces/Sample/catalog/%5BSample%5DDev%20%26%20Test%20Environment%20(All-in-One,%20Azure)","method":"DELETE"}]}]';
		const bps = [];
		
		await vscode.commands.executeCommand('list_blueprints', profile)
		.then(async (result:string) => {
			const blueprintsJson = JSON.parse(result);

			const toBp = (blueprintName: string, description: string, is_sample: boolean, inputs: Array<string>, artifacts: string):
			Blueprint => {
				var cleanName = blueprintName;
				if (is_sample)
					cleanName = cleanName.replace('[Sample]', '')
				return new Blueprint(cleanName, description, vscode.TreeItemCollapsibleState.None, {
					command: 'extension.openReserveForm',
					title: '',
					arguments: [blueprintName, inputs, artifacts]
					// arguments: [blueprintName, space, inputs, artifacts]
				});
			};

			for (var b=0; b<blueprintsJson.length; b++) {
				const bpj = blueprintsJson[b];
				if (bpj.errors.length==0 && bpj.enabled) { 
					var bp = toBp(bpj.blueprint_name, bpj.description, bpj.is_sample, bpj.inputs, bpj.artifacts);
					// var bp = toBp(bpj.blueprint_name, bpj.description, bpj.is_sample, conn["space"], bpj.inputs, bpj.artifacts);
					bps.push(bp);
				}
			}		
		})
		return bps;
	}
}

export class Space extends vscode.TreeItem {

	constructor(
		public readonly label: string,
		public readonly collapsibleState: vscode.TreeItemCollapsibleState,
		
	) {
		super(label, collapsibleState);

		this.tooltip = this.label;
	}

	iconPath = {
		light: path.join(__filename, '..', '..', 'resources', 'light', 'folder.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'folder.svg')
	};

	contextValue = 'folder';
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
