$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python-runtime.ps1')
$runtime = Find-WakfuPython
$prefix = $runtime.Arguments
& $runtime.Executable @prefix -X utf8 -B (Join-Path $PSScriptRoot 'launch.py')
if ($LASTEXITCODE -ne 0) { throw 'Le lancement de WAKFU Atlas a échoué.' }
