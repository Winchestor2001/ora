@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo =====================================================
echo   MAX Channel Viewer — сборка MaxViewer.exe
echo =====================================================
echo.

REM 1. Найти Python (py или python)
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo [X] Python не найден.
    echo     Установите Python 3.10+ с https://www.python.org/downloads/
    echo     При установке отметьте "Add Python to PATH", затем запустите снова.
    pause
    exit /b 1
)
echo [+] Python: !PY!
!PY! --version

REM 2. Окружение сборки
echo.
echo [+] Создаю окружение сборки (buildenv)...
!PY! -m venv buildenv
if errorlevel 1 ( echo [X] Не удалось создать venv. & pause & exit /b 1 )
call buildenv\Scripts\activate.bat

REM 3. Зависимости (httpx, colorama, pyinstaller)
echo.
echo [+] Устанавливаю зависимости сборки...
python -m pip install --upgrade pip --quiet
python -m pip install -r requirements-build.txt
if errorlevel 1 ( echo [X] Ошибка установки зависимостей. & pause & exit /b 1 )

REM 4. Сборка одного .exe
echo.
echo [+] Собираю MaxViewer.exe (это займёт минуту)...
pyinstaller --noconfirm --clean --onefile --console ^
    --name MaxViewer ^
    --collect-submodules cli ^
    --hidden-import colorama ^
    main.py
if errorlevel 1 ( echo [X] Сборка не удалась. & pause & exit /b 1 )

echo.
echo =====================================================
echo   Готово!  Файл: dist\MaxViewer.exe
echo =====================================================
echo.
echo Передайте пользователю dist\MaxViewer.exe (см. client-dist\README.txt).
echo.
pause
endlocal
