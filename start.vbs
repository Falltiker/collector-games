Set objShell = CreateObject("WScript.Shell")
Set objFSO = CreateObject("Scripting.FileSystemObject")

strScriptPath = objFSO.GetParentFolderName(WScript.ScriptFullName)

objShell.Run """" & strScriptPath & "\venv\Scripts\python.exe"" """ & strScriptPath & "\main.py""", 0, False

Set objShell = Nothing
Set objFSO = Nothing