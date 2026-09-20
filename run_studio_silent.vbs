Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "D:\work\dev\ebook"
WshShell.Run """C:\Users\lmo03\AppData\Local\Programs\Python\Python312\pythonw.exe"" ebook_studio_gui.py", 0, False
