@echo off
chcp 65001 >nul
REM ============================================================
REM   MiniOyinlar — Windows uchun .exe yasash skripti
REM ============================================================
REM   Foydalanish:
REM     1) Bu papkani Windows kompyuterga ko'chiring
REM        (launcher.py, platformer.py, space_game.py shu papkada bo'lsin)
REM     2) python.org dan Python 3.10+ o'rnating
REM        (o'rnatishda "Add Python to PATH" katagiga belgi qo'ying!)
REM     3) Shu faylni ikki marta bosing (yoki cmd da ishga tushiring)
REM
REM   Natija:  dist\MiniOyinlar.exe  — bitta fayl, ikki marta bosib o'ynaladi
REM ============================================================

echo.
echo === [1/2] Kerakli kutubxonalar o'rnatilmoqda... ===
python -m pip install --upgrade pip
python -m pip install pygame numpy pyinstaller
if errorlevel 1 (
    echo.
    echo XATO: kutubxonalar o'rnatilmadi. Python to'g'ri o'rnatilganini tekshiring.
    echo "python --version" buyrug'i ishlashi kerak.
    pause
    exit /b 1
)

echo.
echo === [2/2] MiniOyinlar.exe yasalmoqda (1-2 daqiqa)... ===
python -m PyInstaller --noconfirm --onefile --windowed ^
  --name "MiniOyinlar" ^
  --hidden-import platformer ^
  --hidden-import space_game ^
  launcher.py
if errorlevel 1 (
    echo.
    echo XATO: .exe yasalmadi. Yuqoridagi xabarlarni tekshiring.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   TAYYOR!  Natija:  dist\MiniOyinlar.exe
echo   Shu faylni ikki marta bosib o'ynashingiz mumkin.
echo ============================================================
pause
