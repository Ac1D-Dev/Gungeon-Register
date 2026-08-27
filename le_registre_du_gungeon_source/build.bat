@echo off
setlocal
title Construction de Le Registre du Gungeon (.exe)
cd /d "%~dp0"

echo =====================================================
echo   Le Registre du Gungeon - construction du .exe
echo =====================================================
echo.
echo Ce script est a lancer UNE SEULE FOIS. Il va :
echo   1. Verifier que Python est installe
echo   2. Installer pywebview et pyinstaller
echo   3. Fabriquer RegistreDuGungeon.exe (fichier unique, autonome)
echo.
echo Connexion internet necessaire pour cette etape.
echo.
pause

where python >nul 2>nul
if errorlevel 1 (
    echo.
    echo [ERREUR] Python n'est pas trouve dans le PATH.
    echo Installez Python depuis https://www.python.org/downloads/
    echo IMPORTANT : cochez bien la case "Add python.exe to PATH" pendant l'installation.
    echo Relancez ensuite ce script.
    echo.
    pause
    exit /b 1
)

if not exist "gungeon_app.py" (
    echo [ERREUR] gungeon_app.py introuvable dans ce dossier.
    pause
    exit /b 1
)
if not exist "gungeon_registre.html" (
    echo [ERREUR] gungeon_registre.html introuvable dans ce dossier.
    pause
    exit /b 1
)
if not exist "guid_map_data.json" (
    echo [ERREUR] guid_map_data.json introuvable dans ce dossier.
    pause
    exit /b 1
)

set ICON_ARG=
if exist "gungeon_icon.ico" (
    set ICON_ARG=--icon "gungeon_icon.ico"
) else (
    echo [INFO] gungeon_icon.ico introuvable, le .exe utilisera l'icone par defaut.
)

set BGVIDEO_ARG=
if exist "background.mp4" (
    set BGVIDEO_ARG=--add-data "background.mp4;."
    echo [INFO] background.mp4 trouve, il sera inclus comme fond d'ecran anime.
)
if not exist "background.mp4" echo [INFO] background.mp4 introuvable, le fond restera le degrade sombre uni ou utilisera background.gif s'il est present.

set BGGIF_ARG=
if exist "background.gif" (
    set BGGIF_ARG=--add-data "background.gif;."
    echo [INFO] background.gif trouve, il sera inclus comme repli si background.mp4 est absent.
)

echo.
echo --- Installation des dependances (peut prendre 1-2 minutes) ---
python -m pip install --upgrade pip
python -m pip install pywebview pyinstaller pythonnet vdf

echo.
echo --- Nettoyage des anciens fichiers de construction (evite un .exe perime) ---
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
if exist "RegistreDuGungeon.spec" del /q "RegistreDuGungeon.spec"

echo.
echo --- Construction du .exe (peut prendre 1-2 minutes) ---
python -m PyInstaller ^
    --onefile ^
    --windowed ^
    --clean ^
    --name "RegistreDuGungeon" ^
    --add-data "gungeon_registre.html;." ^
    --add-data "guid_map_data.json;." ^
    %BGVIDEO_ARG% ^
    %BGGIF_ARG% ^
    --hidden-import webview.platforms.edgechromium ^
    --hidden-import webview.platforms.winforms ^
    --hidden-import clr_loader ^
    --collect-submodules webview ^
    --noconfirm ^
    %ICON_ARG% ^
    gungeon_app.py

if errorlevel 1 (
    echo.
    echo [ERREUR] La construction a echoue - voir le message ci-dessus.
    pause
    exit /b 1
)

if exist "dist\RegistreDuGungeon.exe" (
    copy /y "dist\RegistreDuGungeon.exe" "RegistreDuGungeon.exe" >nul
    echo.
    echo =====================================================
    echo   TERMINE !
    echo   RegistreDuGungeon.exe a ete cree dans ce dossier.
    echo   Vous pouvez desormais le deplacer/copier ou vous
    echo   voulez et le lancer directement, sans Python.
    echo =====================================================
) else (
    echo.
    echo [ERREUR] Le fichier .exe n'a pas ete trouve apres la construction.
)

echo.
pause
