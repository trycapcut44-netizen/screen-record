Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

strScriptDir = fso.GetParentFolderName(WScript.ScriptFullName)

' Check if dist\ZoomRecorder.exe exists first
strExe = strScriptDir & "\dist\ZoomRecorder.exe"
If fso.FileExists(strExe) Then
    WshShell.Run """" & strExe & """", 0, False
Else
    ' Run via pythonw without opening any console/terminal window
    strCmd = "pythonw """ & strScriptDir & "\main.pyw"""
    WshShell.Run strCmd, 0, False
End If
