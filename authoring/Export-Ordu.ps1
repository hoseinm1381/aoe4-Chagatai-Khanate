param(
    [string]$Blender = 'E:\Blender5.2\blender.exe',
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$scratch = 'F:\aoe_4_temp\Temp_aoe4'
$work = Join-Path $scratch ('chagatai-ordu-' + [guid]::NewGuid().ToString('N'))
$extension = Join-Path $env:APPDATA 'Blender Foundation\Blender\5.2\extensions\raw_githubusercontent_com\garrison'
New-Item -ItemType Directory -Path "$work\temp" | Out-Null
$previousTemp = $env:TEMP
$previousTmp = $env:TMP
$previousPythonPath = $env:PYTHONPATH
$previousNoBytecode = $env:PYTHONDONTWRITEBYTECODE
$previousBlenderConfig = $env:BLENDER_USER_CONFIG
try {
    $env:TEMP = "$work\temp"
    $env:TMP = $env:TEMP
    $env:PYTHONPATH = $extension
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:BLENDER_USER_CONFIG = "$work\blender-config"
    $donor = "$work\lifecycle.rgo"
    & $Python -B -c 'import sys; from pathlib import Path; from garrison_shared import stock_game; stem="art/civilizations/chinese/structures/wonder_forbidden_palace/chi_wonder_forbidden_palace_control_age04/chi_wonder_forbidden_palace_control_age04"; Path(sys.argv[1]).write_bytes(stock_game.current().model_files(stem, required=(".rgo",))[".rgo"])' $donor
    if ($LASTEXITCODE) { throw "Could not read the installed lifecycle donor. Inspect $work" }
    & $Python -B "$PSScriptRoot\ordu_atlas.py" "$work\model"
    if ($LASTEXITCODE) { throw "Could not generate the atlas. Inspect $work" }
    & $Blender --background --factory-startup --python-exit-code 1 --python "$PSScriptRoot\ordu.py" -- "$work\model" "$PSScriptRoot\templates" $donor
    if ($LASTEXITCODE) { throw "Blender export failed. Inspect $work" }
    Write-Output "Editable art and unqualified model-conversion inputs are in $work\model"
}
finally {
    $env:TEMP = $previousTemp
    $env:TMP = $previousTmp
    $env:PYTHONPATH = $previousPythonPath
    $env:PYTHONDONTWRITEBYTECODE = $previousNoBytecode
    $env:BLENDER_USER_CONFIG = $previousBlenderConfig
}
