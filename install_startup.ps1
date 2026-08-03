$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Companion = Join-Path $Root "companion"
$PythonW = Join-Path $Companion ".venv\Scripts\pythonw.exe"
$Main = Join-Path $Companion "main.py"

if (-not (Test-Path $PythonW)) {
    throw "Run setup_and_run.bat before enabling startup."
}

$Startup = [Environment]::GetFolderPath("Startup")
$ShortcutPath = Join-Path $Startup "Universal Media Controller V8.lnk"

$Shell = New-Object -ComObject WScript.Shell
$Shortcut = $Shell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $PythonW
$Shortcut.Arguments = "`"$Main`""
$Shortcut.WorkingDirectory = $Companion
$Shortcut.Save()

Write-Host "Startup shortcut created:"
Write-Host $ShortcutPath
