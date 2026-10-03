On Error Resume Next
Set files = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")
If Err.Number <> 0 Then WScript.Quit 1
project = files.GetParentFolderName(WScript.ScriptFullName)
python = project & "\.venv\Scripts\pythonw.exe"
If Not files.FileExists(python) Then
    Set logFile = files.OpenTextFile(project & "\codekey.log", 8, True)
    logFile.WriteLine "CodeKey setup is missing. Run setup_windows.bat first."
    logFile.Close
    WScript.Quit 1
End If
shell.CurrentDirectory = project
shell.Run """" & python & """ """ & project & "\launch.pyw" & """", 0, False
If Err.Number <> 0 Then
    Set logFile = files.OpenTextFile(project & "\codekey.log", 8, True)
    logFile.WriteLine "CodeKey could not start: " & Err.Description
    logFile.Close
    WScript.Quit 1
End If
