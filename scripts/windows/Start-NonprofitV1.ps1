[CmdletBinding()]
param([ValidateRange(1024,65535)][int]$Port=8643,[switch]$EnableTelegram,[switch]$EnableGoogle)
$ErrorActionPreference='Stop'
$profileRoot='C:\Users\fallo\AppData\Local\hermes\profiles\nonprofit-v1'
$sharedHome='C:\Users\fallo\AppData\Local\hermes'
$hermesExe='C:\Users\fallo\AppData\Local\hermes\staging\non-profit-hermes-v1\20260804T170601Z\telegram-canary-remediation-20260805T100000Z\venv-telegram-fresh\Scripts\python.exe'
$logDir=Join-Path $profileRoot 'logs';$startupLog=Join-Path $logDir 'v1-startup.log';$fatalLog=Join-Path $logDir 'v1-fatal.log';$stdout=Join-Path $logDir 'v1-gateway.stdout.log';$stderr=Join-Path $logDir 'v1-gateway.stderr.log'
try {
 New-Item -ItemType Directory -Force -Path $logDir|Out-Null
 Add-Content -LiteralPath $startupLog -Value ("START " + [DateTime]::UtcNow.ToString('o') + " profile=nonprofit-v1 port="+$Port+" telegram="+$EnableTelegram+" google="+$EnableGoogle)
 if(-not(Test-Path -LiteralPath $hermesExe)){throw 'V1 Hermes executable unavailable'}
 $env:HERMES_HOME=$profileRoot;$env:DATA_DIR=Join-Path $profileRoot 'data';$env:STATE_DIR=Join-Path $profileRoot 'state';$env:PUBLIC_DIR=Join-Path $profileRoot 'public';$env:API_SERVER_ENABLED='1';$env:API_SERVER_HOST='127.0.0.1';$env:API_SERVER_PORT=[string]$Port;$env:API_SERVER_KEY='DISABLED_OFFLINE';$env:HERMES_TELEGRAM_POST_CONNECT_MUTATIONS='0';$env:HERMES_TELEGRAM_DISABLE_FALLBACK_IPS='1'
 foreach($k in @('TELEGRAM_BOT_TOKEN','TELEGRAM_ALLOWED_USERS','TELEGRAM_HOME_CHANNEL','TELEGRAM_SOURCE_SCOPE','NON_PROFIT_HERMES_CREDENTIALS_FILE','NON_PROFIT_HERMES_SPREADSHEET_ID','NON_PROFIT_HERMES_CALENDAR_ID')){Remove-Item ('Env:'+$k) -ErrorAction SilentlyContinue}
 $map=@{};foreach($line in Get-Content -LiteralPath (Join-Path $profileRoot 'private\configuration\bindings.env')){if($line -match '^([A-Z0-9_]+)=(.*)$'){$map[$matches[1]]=$matches[2]}}
 if($EnableTelegram){foreach($k in @('TELEGRAM_BOT_TOKEN','TELEGRAM_ALLOWED_USERS','TELEGRAM_HOME_CHANNEL','TELEGRAM_SOURCE_SCOPE')){if($map.ContainsKey($k)){Set-Item ('Env:'+$k) $map[$k]}};if(-not $env:TELEGRAM_BOT_TOKEN -or -not $env:TELEGRAM_ALLOWED_USERS){throw 'Required private Telegram bindings unavailable'}}
 if($EnableGoogle){foreach($k in @('NON_PROFIT_HERMES_SPREADSHEET_ID','NON_PROFIT_HERMES_CALENDAR_ID')){if($map.ContainsKey($k)){Set-Item ('Env:'+$k) $map[$k]}};$env:NON_PROFIT_HERMES_CREDENTIALS_FILE=Join-Path $profileRoot 'private\google\google_token.json';if(-not(Test-Path -LiteralPath $env:NON_PROFIT_HERMES_CREDENTIALS_FILE)){throw 'Private Google credential copy unavailable'}}
 Set-Location -LiteralPath $profileRoot
 $p=Start-Process -FilePath $hermesExe -ArgumentList @('C:\Users\fallo\non-profit-hermes-mvp\scripts\nonprofit_gateway_entry.py','--profile','nonprofit-v1','gateway','run') -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru -WindowStyle Hidden
 Add-Content -LiteralPath $startupLog -Value ("CHILD_STARTED " + $p.Id)
 Wait-Process -Id $p.Id
 Add-Content -LiteralPath $startupLog -Value ("CHILD_EXIT " + $p.ExitCode)
 exit $p.ExitCode
} catch {New-Item -ItemType Directory -Force -Path $logDir|Out-Null;Add-Content -LiteralPath $fatalLog -Value (([DateTime]::UtcNow.ToString('o'))+' '+$_.Exception.Message);exit 1}

