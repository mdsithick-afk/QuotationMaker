@echo off
REM ===== Quotation Maker - build script (Windows 11) =====
REM Needs: Python 3.10+ (python.org, tick "Add to PATH" and "tcl/tk") and Inno Setup 6 (jrsoftware.org)
cd /d "%~dp0"
py -m pip install --upgrade pip
py -m pip install -r requirements.txt || goto :err
py -m PyInstaller --noconfirm --clean --windowed --name QuotationMaker --icon icon.ico app.py || goto :err
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% (
  echo Inno Setup 6 not found. Install it from https://jrsoftware.org/isinfo.php and run build.bat again.
  goto :err
)
%ISCC% installer.iss || goto :err
echo.
echo DONE. Your setup file is in the "Output" folder: QuotationMaker_Setup.exe
pause
exit /b 0
:err
echo BUILD FAILED - see messages above.
pause
exit /b 1
