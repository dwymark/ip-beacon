# Run the ip-beacon sender on Windows, for a laptop whose Linux side cannot reach the LAN, such as WSL2 in mirrored
# mode while a VPN like Mullvad is connected. Copies ip-beacon.py to %LOCALAPPDATA%\ip-beacon, beside a pythonw
# wrapper that sets BEACON_ADDR, and registers a task for this user that starts it at logon and now. No elevation.
#
#   powershell -ExecutionPolicy Bypass -File install-windows.ps1 [-Address 192.168.1.255] [-Remove]
#
# Address is the LAN's broadcast address: Windows sends the limited broadcast address out the default route, which a
# VPN takes off the LAN.
param(
    [string]$Address = '192.168.1.255',
    [switch]$Remove
)

$ErrorActionPreference = 'Stop'
$task = 'ip-beacon'
$dir = Join-Path $env:LOCALAPPDATA 'ip-beacon'

if (Get-ScheduledTask -TaskName $task -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $task
    Unregister-ScheduledTask -TaskName $task -Confirm:$false
}
if ($Remove) {
    Remove-Item -Recurse -Force $dir -ErrorAction SilentlyContinue
    Write-Output "Removed the $task task and $dir."
    return
}

$pythonw = (Get-Command pythonw.exe).Source
New-Item -ItemType Directory -Force $dir | Out-Null
Copy-Item (Join-Path $PSScriptRoot 'ip-beacon.py') $dir -Force
@"
import os, runpy
os.environ["BEACON_ADDR"] = "$Address"
runpy.run_path(os.path.join(os.path.dirname(__file__), "ip-beacon.py"), run_name="__main__")
"@ | Set-Content -Encoding ascii (Join-Path $dir 'ip-beacon.pyw')

$action = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$(Join-Path $dir 'ip-beacon.pyw')`"" -WorkingDirectory $dir
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $task -Action $action -Trigger $trigger -Settings $settings `
    -Description 'Broadcast this host''s name and IP over UDP (ip-beacon)' | Out-Null
Start-ScheduledTask -TaskName $task
Write-Output "Registered and started the $task task, broadcasting to $Address."
