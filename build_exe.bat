@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
echo ============================================
echo   ELIOT - Construction de ELIOT.exe
echo ============================================

where python >nul 2>nul
if errorlevel 1 (
  echo [ERREUR] Python 3.11 ou 3.12 est requis : https://www.python.org/downloads/
  echo Coche "Add python.exe to PATH" pendant l'installation.
  pause
  exit /b 1
)

if not exist .venv (
  echo [1/6] Creation de l'environnement virtuel...
  python -m venv .venv || goto :error
)
call .venv\Scripts\activate.bat

echo [2/6] Installation des dependances...
python -m pip install --upgrade pip >nul
pip install -r requirements.txt || goto :error
pip install emergentintegrations --extra-index-url https://d33sy5i8bnduwe.cloudfront.net/simple/ || goto :error

echo [3/6] Installation du navigateur Chromium (Playwright)...
echo         Dossier : %%LOCALAPPDATA%%\ms-playwright (relu par ELIOT.exe au lancement)
python -m playwright install chromium || goto :error

echo [4/6] Generation de l'icone...
python tools\make_icon.py || goto :error

echo [5/6] Tests automatises...
python -m pytest -q || goto :error

echo [6/6] Construction de l'executable...
pyinstaller --noconfirm --clean eliot.spec || goto :error

echo.
echo ============================================
echo  Termine ! Executable : dist\ELIOT\ELIOT.exe
echo  Pour un installateur : ouvre installer\eliot.iss avec Inno Setup.
echo ============================================
pause
exit /b 0

:error
echo.
echo [ERREUR] La construction a echoue. Lis le message ci-dessus.
pause
exit /b 1
