export const loginFormHtml = `
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

<style>
        div {
            margin-bottom: 10px;
        }
        label {
            display: inline-block;
            width: 150px;
            text-align: right;
        }
    </style>
</head>
    <body>
        <div id="app">
            <h1>Login To Torque</h1>

            <div>
                <label for="torque-profile">Profile Name: </label>
                <input id="torque-profile" type="text"> <br>

                <label for="torque-account">Torque Account: </label>
                <input id="torque-account" type="text"><br>

                <label for="torque-space">Torque Space: </label>
                <input id="torque-space" type="text"><br>

                <label for="torque-email">Email: </label>
                <input id="torque-email" type="email"><br>

                <label for="torque-password">Password: </label>
                <input id="torque-password" type="password"> <br>

                <input id="submit" type="submit" value="Login">
            </div>
        </div>
    </body>
    <script>
        const vscode = acquireVsCodeApi();
        document.getElementById("submit").addEventListener("click", function() {
            login();
        });
        function login() {
            vscode.postMessage({
                command: 'login',
                profile: document.getElementById("torque-profile").value,
                account: document.getElementById("torque-account").value,
                space: document.getElementById("torque-space").value,
                email: document.getElementById("torque-email").value,
                password: document.getElementById("torque-password").value
            });
        }
    </script>
</html>`