param([string]$Mode, [string]$PythonPath, [string]$NodePath)
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))

function Resolve-Executable {
    param([string]$Value, [string]$Name)
    if (-not $Value -or $Value -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\]+\\[^\\]+\\)' -or
        [IO.Path]::GetFileName($Value) -ine $Name -or -not (Test-Path -LiteralPath $Value -PathType Leaf)) {
        throw "An explicit existing absolute $Name path is required; no PATH or worktree fallback."
    }
    return (Resolve-Path -LiteralPath $Value).ProviderPath
}

function ConvertTo-NativeArgument {
    param([string]$Value)
    return '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}

function Invoke-IsolatedTool {
    param([string]$Executable, [string[]]$Arguments, [string]$OwnedRoot, [switch]$Probe)
    $start = New-Object Diagnostics.ProcessStartInfo
    $start.FileName = $Executable
    $start.Arguments = ($Arguments | ForEach-Object { ConvertTo-NativeArgument $_ }) -join ' '
    $start.WorkingDirectory = $OwnedRoot
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.RedirectStandardOutput = $true
    $start.RedirectStandardError = $true
    $start.StandardOutputEncoding = $utf8NoBom
    $start.StandardErrorEncoding = $utf8NoBom
    $start.EnvironmentVariables.Clear()
    foreach ($key in @('SystemRoot', 'WINDIR', 'COMSPEC', 'SYSTEMDRIVE')) {
        $value = [Environment]::GetEnvironmentVariable($key)
        if ($value) { $start.EnvironmentVariables[$key] = $value }
    }
    foreach ($key in @('HOME', 'USERPROFILE', 'APPDATA', 'LOCALAPPDATA', 'TEMP', 'TMP', 'TMPDIR')) {
        $start.EnvironmentVariables[$key] = $OwnedRoot
    }
    $start.EnvironmentVariables['PYTHONUTF8'] = '1'
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $start
    try {
        if (-not $process.Start()) { throw 'Cannot start approved executable.' }
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if ($Probe -and -not $process.WaitForExit(30000)) {
            $process.Kill()
            $process.WaitForExit()
            throw 'Executable compatibility probe timed out.'
        }
        $process.WaitForExit()
        return [pscustomobject]@{ Code = $process.ExitCode; Output = $stdout.Result; Error = $stderr.Result }
    }
    finally { $process.Dispose() }
}

function Require-Success {
    param($Result)
    if ($Result.Output) { Write-Host $Result.Output }
    if ($Result.Error) { [Console]::Error.WriteLine($Result.Error) }
    if ($Result.Code -ne 0) { throw "Verification child failed: $($Result.Code)" }
}

function Run-Step {
    param([string]$Name, [scriptblock]$Command)
    Write-Host "==> $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) { throw "$Name failed: $LASTEXITCODE" }
}

$ownedRoot = $null
$exitCode = 0
try {
    if ($Mode -cnotin @('TestOnly', 'BuildChecks')) { throw 'Explicit -Mode TestOnly or -Mode BuildChecks is required.' }
    $python = Resolve-Executable $PythonPath 'python.exe'
    $node = Resolve-Executable $NodePath 'node.exe'
    $ownedRoot = Join-Path ([IO.Path]::GetTempPath()) ('stockboda-wrapper-' + [guid]::NewGuid().ToString('N'))
    $null = New-Item -ItemType Directory -Path $ownedRoot
    $pythonProbe = Invoke-IsolatedTool $python @('-I', '-X', 'utf8', '-B', '-c', "import sys, sqlite3, unittest; print('H4_PYTHON:'+str(sys.version_info.major)+'.'+str(sys.version_info.minor))") $ownedRoot -Probe
    if ($pythonProbe.Code -ne 0 -or $pythonProbe.Output.Trim() -notmatch '^H4_PYTHON:3\.(1[1-9]|[2-9][0-9])$') {
        throw 'Compatible Python 3.11+ is required.'
    }
    $nodeProbe = Invoke-IsolatedTool $node @('--permission', '--test-isolation=none', '--version') $ownedRoot -Probe
    if ($nodeProbe.Code -ne 0 -or $nodeProbe.Output.Trim() -notmatch '^v(2[4-9]|[3-9][0-9])\.\d+\.\d+$') {
        throw 'Compatible Node 24+ is required.'
    }
    if ($Mode -ceq 'TestOnly') {
        $coordinator = Join-Path $root 'tests\run_isolated_tests.py'
        Require-Success (Invoke-IsolatedTool $python @('-I', '-X', 'utf8', '-B', $coordinator, '--all') $ownedRoot)
        Require-Success (Invoke-IsolatedTool $python @('-I', '-X', 'utf8', '-B', $coordinator, '--node-all', '--node-executable', $node) $ownedRoot)
    }
    else {
        # BuildChecks is NOT the H4 boundary or release/deploy approval.
        $npm = Join-Path (Split-Path -Parent $node) 'npm.cmd'
        if (-not (Test-Path -LiteralPath $npm -PathType Leaf)) { throw 'npm.cmd must exist beside approved Node.' }
        $oldEnvironment = @{}
        foreach ($key in @('VITE_APP_NAME', 'npm_config_update_notifier', 'PYTHONUTF8', 'PATH')) {
            $oldEnvironment[$key] = [Environment]::GetEnvironmentVariable($key)
        }
        Push-Location $root
        try {
            $env:PYTHONUTF8 = "1"
            $env:npm_config_update_notifier = 'false'
            $env:PATH = (Split-Path -Parent $node) + [IO.Path]::PathSeparator + $env:PATH
            Run-Step "Backend compile check" { & $python -m compileall backend }
            Run-Step "Tracked secret scan" { & $python scripts\check_no_tracked_secrets.py }
            Set-Location (Join-Path $root 'frontend')
            Run-Step "Frontend lint" { & $npm run lint }
            if (-not $env:VITE_APP_NAME) { $env:VITE_APP_NAME = 'StockBoda' }
            Run-Step "Frontend production build" { & $npm run build }
        }
        finally {
            Pop-Location
            foreach ($key in $oldEnvironment.Keys) { [Environment]::SetEnvironmentVariable($key, $oldEnvironment[$key]) }
        }
    }
}
catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    $exitCode = 2
}
finally {
    if ($ownedRoot) {
        try {
            $tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
            if (-not ([IO.Path]::GetFullPath($ownedRoot).StartsWith($tempBase)) -or (Split-Path -Leaf $ownedRoot) -notlike 'stockboda-wrapper-*') { throw 'Unsafe cleanup path' }
            Remove-Item -LiteralPath $ownedRoot -Recurse -Force
        }
        catch { [Console]::Error.WriteLine('Wrapper temporary cleanup failed.'); $exitCode = 2 }
    }
}
exit $exitCode
