@echo off
echo ===================================================
echo   Building ZoomRecorder Pro Standalone Executable
echo ===================================================
echo.

echo Verifying dependencies...
python -m pip install --upgrade -r requirements.txt pyinstaller pillow

echo.
echo Building executable with PyInstaller (No Console + Custom Icon)...
pyinstaller --onefile --windowed --noconsole --name ZoomRecorder --icon=icon.ico --add-data "icon.ico;." --add-data "icon.png;." --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 --hidden-import=win32gui --hidden-import=win32con --hidden-import=sounddevice main.py

echo.
if exist "dist\ZoomRecorder.exe" (
    echo ===================================================
    echo   BUILD SUCCESSFUL!
    echo   Executable located at: dist\ZoomRecorder.exe
    echo   Icon: Custom ZoomRecorder Pro Icon embedded
    echo   Window Mode: Clean GUI (No black terminal window)
    echo ===================================================
) else (
    echo [ERROR] Build failed. Please inspect the output above.
)
pause
