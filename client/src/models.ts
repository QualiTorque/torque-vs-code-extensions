import * as vscode from 'vscode';
import * as path from 'path';


export class Sandbox extends vscode.TreeItem {
	constructor(
		public readonly label: string,
		public readonly collapsibleState: vscode.TreeItemCollapsibleState,
		public id: string,
		public blueprint_name: string,
		public readonly command?: vscode.Command,

	) {
		super(label, collapsibleState);

		this.tooltip = `Originated from the blueprint '${this.blueprint_name}'`;
		this.description = this.id;
	}

	iconPath = {
		light: path.join(__filename, '..', '..', 'resources', 'light', 'dependency.svg'),
		dark: path.join(__filename, '..', '..', 'resources', 'dark', 'dependency.svg')
	};

	contextValue = 'dependency';
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

export class Blueprint extends vscode.TreeItem {

	constructor(
		public readonly label: string,
		public readonly description: string,
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