# create_shortcut.ps1
# Creates a desktop shortcut for xobliam

$ErrorActionPreference = "Stop"

# Get paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "xobliam.lnk"
$targetPath = Join-Path $scriptDir "run_xobliam.bat"
$iconPath = Join-Path $scriptDir "xobliam.ico"

# Verify required files exist
if (-not (Test-Path $targetPath)) {
    Write-Error "run_xobliam.bat not found at: $targetPath"
    exit 1
}

if (-not (Test-Path $iconPath)) {
    Write-Error "xobliam.ico not found at: $iconPath"
    exit 1
}

# Create the shortcut using WScript.Shell COM object
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)

$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $scriptDir
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Description = "xobliam - Gmail Analytics Dashboard"
$shortcut.WindowStyle = 1  # Normal window

$shortcut.Save()

Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "Location: $shortcutPath"
Write-Host "Target: $targetPath"
Write-Host "Icon: $iconPath"
