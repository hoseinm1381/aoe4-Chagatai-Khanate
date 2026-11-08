param(
    [ValidateSet('pasture','steppe_hearth')]
    [string[]]$Assets = @('pasture','steppe_hearth'),
    [string]$Blender = 'E:\Blender5.2\blender.exe',
    [string]$Python = 'python'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$scratch = 'F:\aoe_4_temp\Temp_aoe4'
$run = Join-Path $scratch ('cklife-' + [guid]::NewGuid().ToString('N').Substring(0,8))
$previous = @($env:CK_RUN, $env:TEMP, $env:TMP, $env:PYTHONDONTWRITEBYTECODE)
New-Item -ItemType Directory -Path $run | Out-Null
try {
    $env:CK_RUN = $run
    $env:TEMP = $run
    $env:TMP = $run
    $env:PYTHONDONTWRITEBYTECODE = '1'
    foreach ($asset in $Assets) {
        $title = @{pasture='Horse-Pasture'; steppe_hearth='Steppe-Hearth'}[$asset]
        $folder = Join-Path $root ('authoring\review\approval\' + $title.ToLowerInvariant())
        Copy-Item -LiteralPath (Join-Path $folder ('Chagatai-' + $title + '-Lifecycle.blend')) -Destination "$run\$asset-lifecycle.blend"
        & $Blender -b --python-exit-code 1 --python "$PSScriptRoot\texture_inputs.py" -- $asset
        if ($LASTEXITCODE) { throw "Texture extraction failed for $asset" }
        & $Python -B "$PSScriptRoot\bake_atlas.py" $asset
        if ($LASTEXITCODE) { throw "Atlas generation failed for $asset" }
        & $Blender -b --python-exit-code 1 --python "$PSScriptRoot\prepare_stage.py" -- $asset
        if ($LASTEXITCODE) { throw "Native mesh staging failed for $asset" }
        & $Blender -b --python-exit-code 1 --python "$PSScriptRoot\stage_shared_atlas.py" -- "$run\$asset-native-stage.blend" "$root\authoring\cook-template" "$run\$asset" "$run\$asset-atlas" $asset
        if ($LASTEXITCODE) { throw "Content Editor project staging failed for $asset" }
        Write-Output "$run\$asset\garrison_static.aoe4mod"
    }
}
finally {
    $env:CK_RUN, $env:TEMP, $env:TMP, $env:PYTHONDONTWRITEBYTECODE = $previous
}
