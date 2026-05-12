@echo off
chcp 65001 >nul
echo ========================================
echo  Bank Statement Processor - Relevés Bancaires Marocains
echo ========================================
echo.

REM Vérifier si Python est installé
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERREUR] Python n'est pas installé ou n'est pas dans le PATH
    echo Veuillez installer Python 3.8+ depuis https://python.org
    pause
    exit /b 1
)

REM Vérifier l'environnement virtuel
if not exist "venv" (
    echo Création de l'environnement virtuel...
    python -m venv venv
)

call venv\Scripts\activate

REM Installer les dépendances si nécessaire
if not exist "venv\installed" (
    echo Installation des dépendances...
    pip install -r requirements.txt
    type nul > venv\installed
)

REM Exécuter le programme avec les arguments passés
python main.py %*

deactivate
pause
