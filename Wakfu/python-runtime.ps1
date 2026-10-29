# Locate an installed Python 3.10+ without a user-specific path.
function Find-WakfuPython {
    foreach ($candidate in @('py', 'python', 'python3')) {
        $command = Get-Command $candidate -CommandType Application -ErrorAction SilentlyContinue
        if (-not $command) { continue }
        # Windows Store aliases can open an installer instead of an interpreter.
        if ($candidate -ne 'py' -and $command.Source -match '\\WindowsApps\\') { continue }
        $prefix = @()
        if ($candidate -eq 'py') { $prefix = @('-3') }
        try {
            $version = & $command.Source @prefix -c "import sys; print('WAKFU_PYTHON_OK' if sys.version_info >= (3,10) else 'OLD')" 2>$null
            if ($LASTEXITCODE -eq 0 -and $version -eq 'WAKFU_PYTHON_OK') {
                return @{ Executable = $command.Source; Arguments = $prefix }
            }
        } catch { }
    }
    throw "Python 3.10 ou plus est nécessaire. Installez Python depuis https://www.python.org/downloads/ avec le lanceur Python ou l'option PATH, puis relancez Ouvrir-Wakfu.cmd."
}
