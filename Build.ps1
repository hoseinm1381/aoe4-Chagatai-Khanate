param(
    [string]$Editor = (Join-Path $env:LOCALAPPDATA 'Garrison\Kit\tools\essence-object-editor\EssenceEditor.exe'),
    [string]$Python = 'python',
    [string]$Scratch = (Join-Path ([IO.Path]::GetTempPath()) 'chagatai-builds')
)
$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$scratch = [IO.Path]::GetFullPath($Scratch)
$work = Join-Path $scratch ('chagatai-build-' + [guid]::NewGuid().ToString('N'))
$extension = if ($env:GARRISON_EXTENSION) { $env:GARRISON_EXTENSION } else {
    Join-Path $env:APPDATA 'Blender Foundation\Blender\5.2\extensions\raw_githubusercontent_com\garrison'
}
$core = Join-Path $extension 'bin\core\garrison-core.exe'
foreach ($required in $core,$Editor) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw "Missing build tool $required" }
}
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousNoBytecode = $env:PYTHONDONTWRITEBYTECODE
$previousPythonPath = $env:PYTHONPATH
$previousScratch = $env:CK_SCRATCH
try {
    $env:CK_SCRATCH = $scratch
    $env:PYTHONPATH = "$root/.tools/python313;$previousPythonPath"
    New-Item -ItemType Directory -Path "$work\temp","$work\library" | Out-Null
    $env:TEMP = "$work\temp"
    $env:TMP = $env:TEMP
    $env:PYTHONDONTWRITEBYTECODE = '1'

    & $core civilization-authoring "$root\source\authoring-profile.json" --library "$work\library"
    if ($LASTEXITCODE) { throw "Carrier authoring failed. Inspect $work" }
    $carrier = "$work\library\Mods\chagatai"
    $images = "$carrier\project\source\ui\images\garrison\chagatai\presentation"
    New-Item -ItemType Directory -Path $images | Out-Null
    Get-ChildItem -LiteralPath "$root\source\presentation" -Filter 'flag_*.png' | Copy-Item -Destination $images
    Copy-Item -LiteralPath "$root\source\presentation\cover.png" -Destination "$carrier\project\source\mod.png"
    & $core mod-project cook --project $carrier --editor $Editor --timeout 600
    if ($LASTEXITCODE) { throw "Carrier cook failed. Inspect $work" }

    Copy-Item -LiteralPath "$root\source\tuning" -Destination "$work\tuning" -Recurse
    & $core essence build-mod --editor $Editor --mod "$work\tuning\chagatai_khanate.aoe4mod" --run-root "$work\tuning-burn" --timeout 600
    if ($LASTEXITCODE) { throw "Tuning cook failed. Inspect $work" }
    $archives = @(Get-ChildItem -LiteralPath "$work\tuning-burn\output" -Filter '*.sga' -Recurse -File)
    if ($archives.Count -ne 1) { throw 'Expected one fresh tuning archive.' }

    $carrierArchive = "$carrier\dist\chagatai.sga"
    $tuningArchive = $archives[0].FullName
    $visuals = "$root\source\visuals"

    & $Python -B "$root\tools\build.py" --carrier $carrierArchive --tuning $tuningArchive --work "$work\baseline"
    if ($LASTEXITCODE) { throw "Gameplay baseline assembly failed. Inspect $work" }
    & $Python -B "$root\tools\build.py" --carrier $carrierArchive --tuning $tuningArchive --work "$work\assembly" --visuals $visuals
    if ($LASTEXITCODE) { throw "Garrison assembly failed. Inspect $work" }

    $receipt = "$work\assembly\verification.json"
    $build = Get-Content -LiteralPath $receipt -Raw | ConvertFrom-Json -AsHashtable
    $zip = $build.zip
    $zipName = Split-Path -Leaf $zip
    & $Python -B "$root\tools\verify_visual_zip.py" $zip $receipt $visuals "$work\baseline\readback" "$work\verified"
    if ($LASTEXITCODE) { throw "Player ZIP verification failed. Inspect $work" }
    & $Python -B "$root\tools\verify_lifecycle018.py" "$work\verified\readback" "$work\verified\lifecycle-verification.json"
    if ($LASTEXITCODE) { throw "Lifecycle/trade contract verification failed. Inspect $work" }
    $build.zip = "release/$zipName"
    $build.carrier_sha256 = (Get-FileHash -LiteralPath $carrierArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    $build.tuning_sha256 = (Get-FileHash -LiteralPath $tuningArchive -Algorithm SHA256).Hash.ToLowerInvariant()
    $build.visual_readback = Get-Content -LiteralPath "$work\verified\visual-verification.json" -Raw | ConvertFrom-Json -AsHashtable
    $build.lifecycle_readback = Get-Content -LiteralPath "$work\verified\lifecycle-verification.json" -Raw | ConvertFrom-Json -AsHashtable

    $release = Join-Path $root 'release'
    New-Item -ItemType Directory -Path $release -Force | Out-Null
    $destination = Join-Path $release $zipName
    Copy-Item -LiteralPath $zip -Destination $destination -Force
    if ((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash -ine $build.zip_sha256) {
        throw "Delivered ZIP failed its hash check. Inspect $work"
    }
    $build | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath "$root\BUILD-VERIFICATION.json" -Encoding utf8
    Write-Output "Verified player ZIP at $destination"
    Write-Output "Scratch run: $work"
}
finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    $env:PYTHONDONTWRITEBYTECODE = $previousNoBytecode
    $env:PYTHONPATH = $previousPythonPath
    $env:CK_SCRATCH = $previousScratch
}
