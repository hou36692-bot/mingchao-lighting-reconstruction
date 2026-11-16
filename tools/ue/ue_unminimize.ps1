# Un-minimise the UE editor window without taking focus.
# A minimised editor renders nothing, so HighResShot would queue forever.
# Requires UE_PROJECT (same variable as ue.mjs / vpshot.sh).
$ErrorActionPreference = "Stop"
if (-not $env:UE_PROJECT) { throw "UE_PROJECT is not set (path to the UE project root)" }
$portFile = Join-Path $env:UE_PROJECT "Saved/UE_MCP_Bridge/port.json"
if (-not (Test-Path $portFile)) { throw "Bridge port file not found: $portFile" }
$port = Get-Content $portFile | ConvertFrom-Json
$p = Get-Process -Id $port.pid
Add-Type @'
using System;using System.Runtime.InteropServices;public class W{[DllImport("user32.dll")]public static extern bool ShowWindow(IntPtr h,int c);[DllImport("user32.dll")]public static extern bool IsIconic(IntPtr h);}
'@
if ([W]::IsIconic($p.MainWindowHandle)) {
    [W]::ShowWindow($p.MainWindowHandle, 4) | Out-Null
    Start-Sleep 2
    "restored"
} else {
    "ok"
}
