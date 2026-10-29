$ErrorActionPreference = 'Stop'
$boardDirectory = Split-Path -Parent $PSScriptRoot
$boardCompiler = Join-Path $env:WINDIR 'Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$boardBuilds = @(
    @{ Source='WakfuPanel.cs'; Output='Wakfu-Commandes.exe' },
    @{ Source='LancerSwitcheur.cs'; Output='Wakfu-Fenetres-Combat.exe' },
    @{ Source='LancerWakfu.cs'; Output='Lancer-4-Wakfu.exe' },
    @{ Source='LancerSiteWakfu.cs'; Output='Ouvrir-Wakfu-Atlas.exe' }
)
foreach ($boardBuild in $boardBuilds) {
    $boardArguments = @('/nologo','/target:winexe','/platform:x64','/codepage:65001',
        '/reference:System.Windows.Forms.dll','/reference:System.Drawing.dll','/reference:System.Web.Extensions.dll',
        ('/out:' + (Join-Path $boardDirectory $boardBuild.Output)),
        (Join-Path $PSScriptRoot $boardBuild.Source))
    & $boardCompiler @boardArguments
    if ($LASTEXITCODE -ne 0) { throw ('Compilation impossible : ' + $boardBuild.Output) }
}
