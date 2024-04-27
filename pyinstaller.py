import subprocess

subprocess.Popen(["pyinstaller", "--onefile", "--console", "main.py"])

# --onefile: Tells PyInstaller to bundle everything into a single executable. Without this, PyInstaller will create a folder with the executable and several dependencies alongside it.
# --console: This option is used if your application is a console program (which it is). It ensures that the console window appears when running the executable