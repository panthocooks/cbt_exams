' Double-click once to put a "CBT Interface" shortcut on your Desktop.
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
Set link = shell.CreateShortcut(shell.SpecialFolders("Desktop") & "\CBT Interface.lnk")
link.TargetPath = folder & "\CBT_Interface.bat"
link.WorkingDirectory = folder
link.WindowStyle = 7
link.Description = "Launch the UGC NET CBT practice interface"
link.Save
MsgBox "Shortcut created on your Desktop: CBT Interface", 64, "CBT Interface"
