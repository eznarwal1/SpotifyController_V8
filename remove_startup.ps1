$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "Universal Media Controller.lnk"

if (Test-Path $ShortcutPath) {
    Remove-Item $ShortcutPath -Force
    Write-Host "Startup shortcut removed."
} else {
    Write-Host "Startup shortcut was not found."
}
