param(
    [string]$EditorRoot = 'E:\Games\steamapps\common\Age of Empires IV',
    [string]$PythonPath = 'C:\Users\RS\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe',
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$workspace = Split-Path -Parent $PSScriptRoot
$project = Join-Path $workspace 'chagatai_khanate\chagatai_khanate.aoe4mod'
& $Python -B (Join-Path $PSScriptRoot 'verify_source.py')
if ($LASTEXITCODE -ne 0) { throw 'Source validation failed; build not started.' }
$buildRoot = Join-Path $workspace ('output\build-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
$nativeLogs = Join-Path $buildRoot 'native-logs'
$intermediate = Join-Path $buildRoot 'intermediate'
$burnLog = Join-Path $buildRoot 'burn.log'
New-Item -ItemType Directory -Force -Path $nativeLogs,$intermediate | Out-Null
# Installed Content Editor BuildApplet switches, also used by the local Normal
# reference project. Output is isolated from the user's baseline archive/cache.
$arguments = @('-rtm','--safe_settings','--do_not_restore','--quiet_crash_report',
    '--no_source_control','--log_path',('"'+$nativeLogs+'"'),
    '--build_mod',('"'+$project+'"'),'--build_path',('"'+$buildRoot+'"'),
    '--intermediate_path',('"'+$intermediate+'"'),'--burn_cache_type','Local',
    '--burn_max_threads','1','--no_burn_window','--burn_platform','PC',
    '--burn_log_path',('"'+$burnLog+'"'))
$started = Get-Date
$stdoutLog=Join-Path $buildRoot 'native-stdout.log'
$stderrLog=Join-Path $buildRoot 'native-stderr.log'
$process = Start-Process -FilePath (Join-Path $EditorRoot 'EssenceEditor.exe') -WorkingDirectory $EditorRoot -ArgumentList $arguments -WindowStyle Hidden -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog -Wait -PassThru
$artifactInfo=@(Get-ChildItem -LiteralPath $buildRoot -Recurse -Filter '*.sga' -File | ForEach-Object { @{path=$_.FullName;bytes=$_.Length} })
$attempt=@{project=$project;started=$started.ToString('o');exit_code=$process.ExitCode;stdout=$stdoutLog;stderr=$stderrLog;burn_log=$burnLog;archives=$artifactInfo;native_validated=$false}
$attempt|ConvertTo-Json -Depth 5|Set-Content -LiteralPath (Join-Path $buildRoot 'build_result.json') -Encoding utf8
if ($process.ExitCode -ne 0) { throw ('Content Editor exited: '+$process.ExitCode) }
if (-not (Test-Path -LiteralPath $burnLog) -or (Get-Item -LiteralPath $burnLog).LastWriteTime -lt $started) { throw 'No fresh burn log; exit code alone is not proof.' }
if ((Get-Item -LiteralPath $burnLog).Length -eq 0) { throw 'Empty burn log; native compilation was not established.' }
if (Select-String -LiteralPath $burnLog -Pattern '^\(E\)' -Quiet) { throw ('Native burn errors: '+$burnLog) }
# Failed initialization can leave a 428-byte SGA header. Reject that artifact
# even if the process exits cleanly. Package member/readback validation follows
# a successful cook and remains a separate gate.
$archives = @(Get-ChildItem -LiteralPath $buildRoot -Recurse -Filter '*.sga' -File | Where-Object { $_.Length -gt 428 -and $_.LastWriteTime -ge $started })
if ($archives.Count -ne 1) { throw 'Expected one fresh native archive containing more than its header.' }
$nativeArchive = $archives[0].FullName
$playable = Join-Path $buildRoot 'chagatai_khanate.sga'
& $Python -B (Join-Path $PSScriptRoot 'landmark_visuals.py') $nativeArchive $playable (Join-Path $buildRoot 'landmarks')
if ($LASTEXITCODE -ne 0) { throw 'Normal landmark binding or package verification failed.' }
Write-Output ('Native archive: '+$nativeArchive)
Write-Output ('Playable archive: '+$playable)
Write-Output ('Burn log: '+$burnLog)
