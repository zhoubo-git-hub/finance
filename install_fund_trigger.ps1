$ErrorActionPreference = 'Stop'

$taskName = 'FundMonitorDaily'
$source = Join-Path $PSScriptRoot 'trigger_fund_monitor.py'
$installDir = Join-Path $env:USERPROFILE 'IdeaProjects\FundMonitorRuntime'
$destination = Join-Path $installDir 'trigger_fund_monitor.py'
$python = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python310\pythonw.exe'

foreach ($required in @($source, $python, 'C:\Program Files\GitHub CLI\gh.exe')) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) {
        throw "Required file missing: $required"
    }
}

$task = Get-ScheduledTask -TaskName $taskName
$originalTriggers = $task.Triggers | Select-Object StartBoundary, Enabled, DaysOfWeek, WeeksInterval | ConvertTo-Json -Compress
$originalPrincipal = $task.Principal | Select-Object UserId, LogonType, RunLevel | ConvertTo-Json -Compress
New-Item -ItemType Directory -Path $installDir -Force | Out-Null
$backup = Join-Path $installDir ("FundMonitorDaily.before-{0}.xml" -f (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
Export-ScheduledTask -TaskName $taskName | Set-Content -LiteralPath $backup -Encoding Unicode

Copy-Item -LiteralPath $source -Destination $destination -Force
if ((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $destination).Hash) {
    throw 'Deployed trigger does not match the source.'
}

$action = New-ScheduledTaskAction -Execute $python -Argument ('"{0}"' -f $destination) -WorkingDirectory $env:SystemRoot
$settings = $task.Settings
$settings.ExecutionTimeLimit = 'PT10M'
Set-ScheduledTask -TaskName $taskName -Action $action -Settings $settings -ErrorAction Stop | Out-Null

$updated = Get-ScheduledTask -TaskName $taskName
$updatedTriggers = $updated.Triggers | Select-Object StartBoundary, Enabled, DaysOfWeek, WeeksInterval | ConvertTo-Json -Compress
$updatedPrincipal = $updated.Principal | Select-Object UserId, LogonType, RunLevel | ConvertTo-Json -Compress
if ($originalTriggers -ne $updatedTriggers -or $originalPrincipal -ne $updatedPrincipal) {
    throw "Unexpected schedule or identity change. Original task is saved at $backup"
}
if ($updated.Actions.Execute -ne $python -or $updated.Actions.Arguments -ne $action.Arguments -or $updated.Actions.WorkingDirectory -ne $env:SystemRoot) {
    throw "Task action verification failed. Original task is saved at $backup"
}

[pscustomobject]@{
    Task = $taskName
    State = $updated.State
    Script = $destination
    Log = (Join-Path $installDir 'fund_trigger.log')
    Backup = $backup
    SchedulePreserved = $true
    IdentityPreserved = $true
} | Format-List
