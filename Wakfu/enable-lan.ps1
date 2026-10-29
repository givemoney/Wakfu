param(
    [Parameter(Mandatory=$true)][string]$LanHost,
    [Parameter(Mandatory=$true)][string]$RemoteSubnet,
    [Parameter(Mandatory=$true)][string]$InterfaceAlias,
    [int]$Port = 8765
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'python-runtime.ps1')
$runtime = Find-WakfuPython
$prefix = $runtime.Arguments
$pythonPath = & $runtime.Executable @prefix -c 'import sys; print(sys.executable)'
if ($LASTEXITCODE -ne 0) { throw 'Interpréteur Python introuvable.' }
$statusPath = Join-Path $PSScriptRoot 'lan-status.json'
try {
    $ruleName = "WAKFU-Atlas-LAN-$Port"
    if (Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue) { throw 'La règle existe déjà ; vérifiez-la avant de la modifier.' }
    New-NetFirewallRule -Name $ruleName -DisplayName 'WAKFU Atlas - consultation réseau local' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -LocalAddress $LanHost -RemoteAddress $RemoteSubnet -InterfaceAlias $InterfaceAlias -Program $pythonPath -Profile Private -EdgeTraversalPolicy Block | Out-Null
    @{ok=$true;rule=$ruleName} | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
} catch {
    @{ok=$false;error=$_.Exception.Message} | ConvertTo-Json | Set-Content -LiteralPath $statusPath -Encoding utf8
    exit 1
}
