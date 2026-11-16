$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$metadata = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $projectRoot 'artifacts/local_model.json') | ConvertFrom-Json
$serverPath = Join-Path $projectRoot $metadata.server_path
$modelPath = Join-Path $projectRoot $metadata.model_path
$runtimeDirectory = Join-Path $projectRoot '.runtime'
$running = Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -eq 'llama-server' -and $_.Path -eq $serverPath }
if ($running) {
    Write-Output 'Project model server is already running.'
    exit 0
}
$serverArguments = @('-m', ('"' + $modelPath + '"'), '--host', '127.0.0.1', '--port', '8087', '-c', '4096', '-t', '4', '-tb', '4', '-np', '1', '--alias', 'day7-qwen2.5-0.5b', '--no-webui')
$serverProcess = Start-Process -FilePath $serverPath -ArgumentList $serverArguments -WorkingDirectory (Split-Path -Parent $serverPath) -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtimeDirectory 'server.stdout.log') -RedirectStandardError (Join-Path $runtimeDirectory 'server.stderr.log')
Set-Content -LiteralPath (Join-Path $runtimeDirectory 'server.pid') -Value $serverProcess.Id -Encoding ASCII
Write-Output ('Started project-only local server PID ' + $serverProcess.Id + ', URL http://127.0.0.1:8087')
