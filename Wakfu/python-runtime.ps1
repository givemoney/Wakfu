﻿# Locate Python without any machine-specific project path.
# Prefer the Python runtime shipped with Wakfu Board, then fall back to a
# system Python 3.10+ for standalone use of the Wakfu subfolder.
function Test-WakfuPython {
    param(
        [Parameter(Mandatory=$true)][string]$Executable,
        [string[]]$Arguments = @()
    )
    try {
        $version = & $Executable @Arguments -c "import sys; print('WAKFU_PYTHON_OK' if sys.version_info >= (3,10) else 'OLD')" 2>$null
        return ($LASTEXITCODE -eq 0 -and $version -eq 'WAKFU_PYTHON_OK')
    } catch {
        return $false
    }
}

function Find-WakfuPython {
    $projectRoot = Split-Path -Parent $PSScriptRoot
    $embedded = Join-Path $projectRoot 'runtime\python.exe'

    if ((Test-Path -LiteralPath $embedded) -and (Test-WakfuPython -Executable $embedded)) {
        return @{ Executable = $embedded; Arguments = @() }
    }

    foreach ($candidate in @('py', 'python', 'python3')) {
        $command = Get-Command $candidate -CommandType Application -ErrorAction SilentlyContinue
        if (-not $command) { continue }

        # Windows Store aliases can open an installer instead of an interpreter.
        if ($candidate -ne 'py' -and $command.Source -match '\\WindowsApps\\') { continue }

        $prefix = @()
        if ($candidate -eq 'py') { $prefix = @('-3') }

        if (Test-WakfuPython -Executable $command.Source -Arguments $prefix) {
            return @{ Executable = $command.Source; Arguments = $prefix }
        }
    }

    throw "Python 3.10 ou plus est nécessaire. Le runtime embarqué du projet est absent ou inutilisable et aucun Python système compatible n'a été trouvé."
}