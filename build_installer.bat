@echo off
echo ===================================================
echo   Building ZoomRecorder Pro Complete Windows Installer
echo ===================================================
echo.

echo [1/3] Checking dependencies...
python -m pip install --upgrade -r requirements.txt pyinstaller pillow

echo.
echo [2/3] Building executable with PyInstaller...
pyinstaller --onefile --windowed --noconsole --name ZoomRecorder --icon=icon.ico --add-data "icon.ico;." --add-data "icon.png;." --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 --hidden-import=win32gui --hidden-import=win32con --hidden-import=sounddevice main.py

if not exist "dist\ZoomRecorder.exe" (
    echo [ERROR] PyInstaller build failed.
    pause
    exit /b 1
)

echo.
echo [3/3] Compiling Setup Installer with Inno Setup...
set "ISCC_PATH=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_PATH%" (
    set "ISCC_PATH=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
)
if not exist "%ISCC_PATH%" (
    set "ISCC_PATH=C:\Program Files\Inno Setup 6\ISCC.exe"
)

"%ISCC_PATH%" "installer.iss"

if exist "Output\ZoomRecorder_Setup.exe" (
    echo.
    echo ===================================================
    echo   INSTALLER CREATED SUCCESSFULLY!
    echo   File: Output\ZoomRecorder_Setup.exe
    echo.
    echo   Yeh ek single setup file hai. Aap kisi ko bhi
    echo   ye file send kar sakte hain. Agla banda is per
    echo   double-click karega to standard software ki tarah
    echo   uske PC me install ho jayega:
    echo     - Desktop par Shortcut banega
    echo     - Start Menu me aayega
    echo     - Control Panel / Windows Settings se Uninstall
    echo       bhi ho sakega
    echo ===================================================
) else (
    echo [ERROR] Inno Setup compilation failed.
)
pause
