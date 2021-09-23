export const loginFormHtml = `
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login to Torque</title>
    {{HEAD_BLOCK}}
        
</head>
    <body>
        <div id="app">
            <h2>Login to Torque</h2>
            <br/>

            <table width='50%' border='0' cellpadding='1' cellspacing='1'>
            <tr><td width='180px'>Profile Name:</td><td><input id="torque-profile" type="text"></td></tr>
            <tr><td width='180px'>Torque Account:</td><td><input id="torque-account" type="text"></td></tr>
            <tr><td width='180px'>Torque Space:</td><td><input id="torque-space" type="text"></td></tr>
            <tr><td width='180px'>Email:</td><td><input id="torque-email" type="email"></td></tr>
            <tr><td width='180px'>Password:</td><td><input id="torque-password" type="password"></td></tr>
            
            <tr><td width='180px'><br/><input id="submit" type="submit" value='Login'></td><td></td></tr>
            </table>
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