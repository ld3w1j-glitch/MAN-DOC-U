@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
echo Maná do Céu - iniciando
if exist ".venv\Scripts\python.exe" goto install
where py >nul 2>nul
if errorlevel 1 goto try_python
py -3 -m venv .venv
if errorlevel 1 goto failed
goto install
:try_python
where python >nul 2>nul
if errorlevel 1 goto missing
python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -c "import sys; assert sys.version_info >= (3, 11), 'Use Python 3.11 ou superior; recomendado 3.12.'"
if errorlevel 1 goto failed
if exist ".venv\mana-requirements.txt" fc /b requirements.txt ".venv\mana-requirements.txt" >nul 2>nul
if exist ".venv\mana-requirements.txt" if not errorlevel 1 goto setup
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
copy /y requirements.txt ".venv\mana-requirements.txt" >nul
:setup
".venv\Scripts\python.exe" scripts\setup.py
if errorlevel 1 goto failed
".venv\Scripts\python.exe" scripts\launch.py
if errorlevel 1 goto failed
exit /b 0
:missing
echo Instale Python 3.12 em https://www.python.org/downloads/ e marque Add Python to PATH.
pause
exit /b 1
:failed
echo Nao foi possivel iniciar. Confira a mensagem acima e o README.md.
pause
exit /b 1
