$ErrorActionPreference='Stop'
$taskName='HermesNonProfit-MemberProjection'
$project='C:\Users\fallo\non-profit-hermes-mvp'
$python='C:\Users\fallo\AppData\Local\hermes\staging\non-profit-hermes-v1\20260804T170601Z\telegram-canary-remediation-20260805T100000Z\venv-telegram-fresh\Scripts\python.exe'
$script=Join-Path $project 'scripts\member_operations_projection.py'
$existing=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if($existing -and ($existing.Actions.Arguments -notlike '*member_operations_projection.py*')){throw 'Existing task ownership unclear'}
$principal=New-ScheduledTaskPrincipal -UserId ($env:USERDOMAIN+'\'+$env:USERNAME) -LogonType S4U -RunLevel Limited
$action=New-ScheduledTaskAction -Execute $python -Argument ('"'+$script+'" --once') -WorkingDirectory $project
$triggers=@((New-ScheduledTaskTrigger -AtStartup),(New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)))
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Description 'One-way sanitized nonprofit Google projection; no SMS or volunteer writes' -Force | Out-Null
Write-Output 'Member projection task installed; no login required.'
