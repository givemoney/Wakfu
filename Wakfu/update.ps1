$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python-runtime.ps1')
$runtime = Find-WakfuPython
$prefix = $runtime.Arguments
& $runtime.Executable @prefix -X utf8 -B (Join-Path $PSScriptRoot 'updater\update.py')
if ($LASTEXITCODE -ne 0) { throw 'La mise à jour WAKFU a échoué.' }
