param([string]$PythonPath, [string]$NodePath, [switch]$BatOnly)
# Synthetic dispatch only. Never run a coordinator suite or BuildChecks.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$utf8NoBom = New-Object Text.UTF8Encoding($false)
$source = [IO.File]::ReadAllText((Join-Path $repo 'scripts/verify_project.ps1'))
$tokens = $null; $errors = $null
$ast = [Management.Automation.Language.Parser]::ParseInput($source, [ref]$tokens, [ref]$errors)
if ($errors.Count) { throw ($errors | Out-String) }
$functions = $ast.FindAll({ param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst] }, $true)
foreach ($name in @('ConvertTo-NativeArgument', 'Invoke-IsolatedTool')) {
    . ([scriptblock]::Create(($functions | Where-Object Name -eq $name).Extent.Text))
}
$tempBase = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$owned = Join-Path $tempBase ('h4-wrapper-regression-' + [guid]::NewGuid().ToString('N'))
$null = New-Item -ItemType Directory -Path $owned
$powershell = Join-Path $PSHOME 'powershell.exe'
$passed = 0
$originalLocation = (Get-Location).Path
$originalNativeDirectory = [Environment]::CurrentDirectory
function Assert-Contract($Condition, $Message) { if (-not $Condition) { throw $Message } }
function Test-BatContract {
    param([string]$CopyRoot, [string]$WorkingRoot)
    $batch = Join-Path $CopyRoot 'verify_project.bat'
    $stub = Join-Path $CopyRoot 'scripts/verify_project.ps1'
    Copy-Item -LiteralPath (Join-Path $repo 'verify_project.bat') -Destination $batch
    [IO.File]::WriteAllText($stub, 'param([int]$Code,$Mode,$PythonPath,$NodePath) [ordered]@{Marker="BAT_STUB";Code=$Code;Pid=$PID;Mode=$Mode;PythonPath=$PythonPath;NodePath=$NodePath;Cwd=(Get-Location).Path} | ConvertTo-Json -Compress; exit $Code')
    $cmd = Join-Path $env:SystemRoot 'System32/cmd.exe'
    Assert-Contract ([IO.Path]::IsPathRooted($cmd) -and (Test-Path -LiteralPath $cmd -PathType Leaf)) 'absolute cmd.exe required'
    foreach ($expected in @(0, 1, 2, 7)) {
        $process = New-Object Diagnostics.Process
        $start = $process.StartInfo
        $start.FileName = $cmd
        # cmd /s /c needs its own outer quote pair, not CRT argument escaping.
        $start.Arguments = '/d /s /c ""' + $batch + '" -Code ' + $expected + ' -Mode TestOnly -PythonPath "C:\approved path\python.exe" -NodePath "C:\approved path\node.exe""'
        $start.WorkingDirectory = $WorkingRoot
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
            $start.EnvironmentVariables[$key] = $WorkingRoot
        }
        Assert-Contract (-not $start.EnvironmentVariables.ContainsKey('PATH') -and -not $start.EnvironmentVariables.ContainsKey('PATHEXT')) 'no PATH/PATHEXT injection'
        $started = $false
        $closed = $false
        $disposed = $false
        try {
            $started = $process.Start()
            Assert-Contract $started 'cmd start'
            $stdout = $process.StandardOutput.ReadToEndAsync()
            $stderr = $process.StandardError.ReadToEndAsync()
            $process.WaitForExit()
            $output = $stdout.GetAwaiter().GetResult()
            $errorText = $stderr.GetAwaiter().GetResult()
            $actual = $process.ExitCode
            Assert-Contract ($process.HasExited -and $stdout.IsCompleted -and $stderr.IsCompleted) 'process/streams incomplete'
            Assert-Contract ($actual -eq $expected) ("BAT expected=$expected actual=$actual stderr=$errorText")
            Assert-Contract ([string]::IsNullOrEmpty($errorText)) ('BAT stderr: ' + $errorText)
            $records = @($output -split '\r?\n' | Where-Object { $_.StartsWith('{') } | ForEach-Object { $_ | ConvertFrom-Json })
            Assert-Contract ($records.Count -eq 1) 'stub must actually execute exactly once'
            $record = $records[0]
            Assert-Contract ($record.Marker -eq 'BAT_STUB' -and $record.Code -eq $expected) 'stub marker/code'
            Assert-Contract ($record.Mode -eq 'TestOnly' -and $record.PythonPath -eq 'C:\approved path\python.exe' -and $record.NodePath -eq 'C:\approved path\node.exe' -and $record.Cwd -eq $WorkingRoot) 'BAT args/external CWD'
            Assert-Contract (-not (Get-Process -Id $record.Pid -ErrorAction SilentlyContinue)) 'stub process still alive'
        }
        finally {
            try {
                if ($started) {
                    $process.StandardOutput.Close()
                    $process.StandardError.Close()
                    $closed = $true
                }
            }
            finally { $process.Dispose(); $disposed = $true }
        }
        Assert-Contract ($closed -and $disposed) 'streams/process not released'
        Write-Output "BAT PASS: expected=$expected actual=$actual stub=true args=true cwd=true exited=true drained=true closed=true disposed=true"
    }
}
try {
    $copy = Join-Path $owned 'checkout with spaces'
    $null = New-Item -ItemType Directory -Path (Join-Path $copy 'scripts') -Force
    if (-not $BatOnly) {
    $py = Join-Path $copy 'python.exe'; $node = Join-Path $copy 'node.exe'
    [IO.File]::WriteAllBytes($py, [byte[]]@())
    [IO.File]::WriteAllBytes($node, [byte[]]@())
    $mock = @'
function Invoke-IsolatedTool {
    param([string]$Executable, [string[]]$Arguments, [string]$OwnedRoot, [switch]$Probe)
    $fault = [IO.File]::ReadAllText((Join-Path $root 'fault.txt'))
    $record = @{ executable=$Executable; arguments=$Arguments; owned=$OwnedRoot; probe=[bool]$Probe }
    Add-Content -LiteralPath (Join-Path $root 'calls.jsonl') -Value ($record | ConvertTo-Json -Compress)
    $output = ''
    if ($Probe -and $Arguments -contains '-c') { $output = 'H4_PYTHON:3.12' }
    elseif ($Probe) { $output = 'v24.15.0' }
    if ($fault -eq 'python-version' -and $Arguments -contains '-c') { $output = 'H4_PYTHON:3.9' }
    if ($fault -eq 'node-version' -and $Arguments -contains '--version') { $output = 'v20.0.0' }
    $code = 0
    if ($fault -eq 'python-failure' -and $Arguments -contains '--all') { $code = 17 }
    if ($fault -eq 'node-failure' -and $Arguments -contains '--node-all') { $code = 19 }
    return [pscustomobject]@{Code=$code; Output=$output; Error=''}
}
'@
    $function = $functions | Where-Object Name -eq 'Invoke-IsolatedTool'
    $synthetic = $source.Substring(0, $function.Extent.StartOffset) + $mock + $source.Substring($function.Extent.EndOffset)
    $wrapper = Join-Path $copy 'scripts/verify_project.ps1'
    [IO.File]::WriteAllText($wrapper, $synthetic, (New-Object Text.UTF8Encoding($true)))
    $good = @('-Mode', 'TestOnly', '-PythonPath', $py, '-NodePath', $node)
    $scenarios = @(
        @{Name='missing-mode'; Args=@(); Calls=0; Code=2},
        @{Name='invalid-mode'; Args=@('-Mode','invalid'); Calls=0; Code=2},
        @{Name='missing-python'; Args=@('-Mode','TestOnly','-NodePath',$node); Calls=0; Code=2},
        @{Name='relative-python'; Args=@('-Mode','TestOnly','-PythonPath','python.exe','-NodePath',$node); Calls=0; Code=2},
        @{Name='absent-python'; Args=@('-Mode','TestOnly','-PythonPath', (Join-Path $owned 'absent/python.exe'),'-NodePath',$node); Calls=0; Code=2},
        @{Name='missing-node'; Args=@('-Mode','TestOnly','-PythonPath',$py); Calls=0; Code=2},
        @{Name='relative-node'; Args=@('-Mode','TestOnly','-PythonPath',$py,'-NodePath','node.exe'); Calls=0; Code=2},
        @{Name='absent-node'; Args=@('-Mode','TestOnly','-PythonPath',$py,'-NodePath',(Join-Path $owned 'absent/node.exe')); Calls=0; Code=2},
        @{Name='python-version'; Args=$good; Calls=1; Code=2},
        @{Name='node-version'; Args=$good; Calls=2; Code=2},
        @{Name='python-failure'; Args=$good; Calls=3; Code=2},
        @{Name='node-failure'; Args=$good; Calls=4; Code=2},
        @{Name='success'; Args=$good; Calls=4; Code=0}
    )
    foreach ($case in $scenarios) {
        [IO.File]::WriteAllText((Join-Path $copy 'fault.txt'), $case.Name)
        $log = Join-Path $copy 'calls.jsonl'
        if (Test-Path -LiteralPath $log) { Remove-Item -LiteralPath $log }
        $result = Invoke-IsolatedTool $powershell (@('-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',$wrapper) + $case.Args) $owned
        Assert-Contract ($result.Code -eq $case.Code) ($case.Name + ': ' + $result.Error)
        $calls = @()
        if (Test-Path -LiteralPath $log) { $calls = @(Get-Content -LiteralPath $log | ForEach-Object { $_ | ConvertFrom-Json }) }
        Assert-Contract ($calls.Count -eq $case.Calls) ($case.Name + ': dispatch count')
        foreach ($call in $calls) { Assert-Contract (-not (Test-Path -LiteralPath $call.owned)) 'wrapper temp residue' }
        if ($case.Name -eq 'success') {
            Assert-Contract (($calls[2].arguments -join '|') -eq ('-I|-B|' + (Join-Path $copy 'tests/run_isolated_tests.py') + '|--all')) 'Python coordinator contract'
            Assert-Contract (($calls[3].arguments -join '|') -eq ('-I|-B|' + (Join-Path $copy 'tests/run_isolated_tests.py') + '|--node-all|--node-executable|' + $node)) 'Node coordinator contract'
            Assert-Contract ($calls[2].executable -eq $py -and $calls[3].executable -eq $py) 'absolute Python dispatch'
        }
        $passed++
        Write-Output ("PASS: " + $case.Name)
    }
    # Exercise the real launcher with harmless interpreter probes only.
    $probe = Invoke-IsolatedTool $PythonPath @('-I','-B','-c', "import os; assert 'PATH' not in os.environ; assert 'PYTHONPATH' not in os.environ; assert 'NODE_OPTIONS' not in os.environ; assert os.environ['HOME']==os.getcwd(); print('clean')") $owned -Probe
    Assert-Contract ($probe.Code -eq 0 -and $probe.Output.Trim() -eq 'clean') ('real sanitized Python probe: ' + $probe.Error)
    $probe = Invoke-IsolatedTool $NodePath @('--permission','--test-isolation=none','--version') $owned -Probe
    Assert-Contract ($probe.Code -eq 0 -and $probe.Output.Trim() -match '^v24\.') 'real Node probe'
    $passed++
    }
    Test-BatContract $copy $owned
    $passed += 4
}
catch { [Console]::Error.WriteLine('PRIMARY: ' + $_.Exception.Message); throw }
finally {
    Set-Location -LiteralPath $originalLocation
    [Environment]::CurrentDirectory = $originalNativeDirectory
    if (-not ([IO.Path]::GetFullPath($owned).StartsWith($tempBase)) -or (Split-Path -Leaf $owned) -notlike 'h4-wrapper-regression-*') { throw 'Unsafe cleanup path' }
    Remove-Item -LiteralPath $owned -Recurse -Force
}
if (Test-Path -LiteralPath $owned) { throw 'Regression temp residue' }
Write-Output "WRAPPER_REGRESSION: $passed PASS; BatOnly=$BatOnly; cleanup=true; root=$owned; BuildChecks/full suites not executed"
