@echo off
echo Creating Desktop Shortcut for ZoomRecorder Pro...

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
"$s=(New-Object -COM WScript.Shell).CreateShortcut([System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'),'ZoomRecorder Pro.lnk')); ^
$s.TargetPath='%~dp0dist\ZoomRecorder.exe'; ^
$s.WorkingDirectory='%~dp0'; ^
$s.IconLocation='%~dp0icon.ico,0'; ^
$s.Description='ZoomRecorder Pro'; ^
$s.Save()"

echo.
echo Desktop shortcut created successfully!
pause
